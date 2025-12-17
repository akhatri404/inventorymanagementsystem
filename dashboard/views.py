from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from products.models import Product
from weekly.models import WeeklyRecord
#from .predict import predict_inventory
from datetime import date, timedelta
from django.contrib import messages
from django.db.models import Max, Subquery, OuterRef, Sum
from django.core.paginator import Paginator

import csv
from django.http import HttpResponse

from django.db.models import Q

def iso_week_to_japanese_label(iso_year: int, iso_week: int) -> str:
    # Monday of ISO week
    monday = date.fromisocalendar(iso_year, iso_week, 1)

    # Sunday-start week (Japanese UI)
    sunday = monday - timedelta(days=1)
    return f"{sunday.strftime('%y')}年{sunday.month}月{sunday.day}日週"

today = date.today()
current_year = today.isocalendar().year
current_week = today.isocalendar().week
week_label = iso_week_to_japanese_label(current_year, current_week)

@login_required
def home(request):
    try:
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        week_label = f"{sunday.strftime('%y')}年{sunday.month}月{sunday.day}日週"

        products = Product.objects.filter(is_active=True)
        # Filters and search
        search = request.GET.get('search','')
        classification_filter = request.GET.get('classification')
        lead_time_filter = request.GET.get('lead_time')

        if search:
            products = products.filter(product_name__icontains=search)|products.filter(jan_code__icontains=search) |products.filter(yayoi_code__icontains=search)
        if classification_filter:
            products = products.filter(classification=classification_filter)
        if lead_time_filter:
            products = products.filter(lead_time=lead_time_filter)
        
        # --- LATEST WEEKLY RECORD ANNOTATIONS ---
        latest_record = WeeklyRecord.objects.filter(
            product=OuterRef('pk')
        ).order_by('-year', '-week_no')

        products = products.annotate(
            latest_incoming=Subquery(latest_record.values('incoming_goods')[:1]),
            latest_outgoing=Subquery(latest_record.values('outgoing_goods')[:1]),
            latest_inventory=Subquery(latest_record.values('inventory')[:1]),
            latest_remaining_weeks=Subquery(latest_record.values('remaining_weeks')[:1]),
        )

        glatest_record = WeeklyRecord.objects.order_by('-year', '-week_no').first()
        latest_week= glatest_record.week_no
        latest_year= glatest_record.year
        latest_label = iso_week_to_japanese_label(latest_year, latest_week)

        #dashboard stats
        total_products = Product.objects.all().count()
        total_inventory = WeeklyRecord.objects.filter(inventory__gt=0).aggregate(total=Sum('inventory'))['total'] or 0
        total_active = products.count()
        total_inactive = Product.objects.filter(is_active=False).count()

        #need_attention = [r for p in products for r in [WeeklyRecord.objects.filter(product=p, year=current_year, week_no=current_week).first()] if r and r.remaining_weeks<=2]
        
        # --- NEED ATTENTION (CURRENT WEEK ONLY) ---
        need_attention = []
        for p in products:
            latest = WeeklyRecord.objects.filter(
                product=p,
                year=latest_year,
                week_no=latest_week
            ).first()

            if latest and latest.remaining_weeks <= 5:
                need_attention.append(latest)

        recently_added = products.order_by('-created_at')[:5]

        # Add the filtered record to each product
        for p in products:
            p.record = p.weeklyrecord_set.filter(year=current_year, week_no=current_week).first()

        # Predictions
        #product_predictions = {p.jan_code:predict_inventory(p,weeks=1) for p in products}

        # --- Pagination ---
        paginator = Paginator(products, 50)  # 50 items per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        # Calculate starting index for serial numbers
        start_index = (page_obj.number - 1) * paginator.per_page

        # Check your existing condition
        has_need_attention = len(need_attention) > 0
        
        # Reset if no attention needed anymore
        if len(need_attention) == 0:
            request.session['need_attention_shown'] = False

        show_modal = False
        if has_need_attention and not request.session.get('need_attention_modal_shown', False):
            show_modal = True
            request.session['need_attention_modal_shown'] = True

        context = {
            'products':page_obj,
            'total_products':total_products,
            'total_inventory':total_inventory,
            'total_active': total_active,
            'total_inactive': total_inactive,
            'need_attention':need_attention,
            'recently_added':recently_added,
            'show_need_attention_popup':show_modal,
            'show_recently_added_popup':len(recently_added)>0,
            'current_year':current_year,
            'current_week':current_week,
            'search':search,
            'classification_filter':classification_filter,
            'lead_time_filter':lead_time_filter,
            'page_obj': page_obj,
            'start_index': start_index,
            'latest_year': latest_year,
            'latest_week': latest_week,
            'week_label': week_label,
            'latest_label': latest_label,
        }
        
        return render(request,'dashboard/home.html', context)
    except Exception as e:
        messages.error(request, "Something went wrong while loading the dashboard.")
        return render(request,'dashboard/home.html', context)

@login_required
def export_csv(request):
    # Get week inputs from GET params (format: "YYYY-Www")
    start_week_value = request.GET.get('start_week', '2020-W01')
    end_week_value = request.GET.get('end_week', '9999-W53')

    # Validate inputs
    if not all([start_week_value, end_week_value]):
        messages.error(request, "Start week and end week are required.")
        return redirect('weekly-summary')

    try:
        # Parse the "YYYY-Www" format
        start_year_str, start_week_str = start_week_value.split('-W')
        end_year_str, end_week_str = end_week_value.split('-W')

        start_year = int(start_year_str)
        start_week = int(start_week_str)
        end_year = int(end_year_str)
        end_week = int(end_week_str)
    except ValueError:
        messages.error(request, "Invalid week format. Use YYYY-Www.")
        return redirect('weekly-summary')

    # Filter records
    records = WeeklyRecord.objects.filter(
        year__gte=start_year,
        year__lte=end_year,
        week_no__gte=start_week,
        week_no__lte=end_week
    ).select_related('product')

    # Build dynamic filename
    filename = f"inventory_export_{start_year}{start_week}_{end_year}{end_week}.csv"

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['年',
        '週',
        '週ラベル',
        '弥生',
        'JAN',
        '商品',
        '分類',
        'LT',
        '規格',
        '月販',
        '予測',
        '入庫',
        '出庫',
        '在庫',
        '残週'
        ])

    for r in records:
        p = r.product
        week_label = iso_week_to_japanese_label(r.year, r.week_no)
        writer.writerow([r.year,
            r.week_no,
            week_label,
            p.yayoi_code,
            p.jan_code,
            p.product_name,
            p.classification,
            p.lead_time,
            p.specifications,
            p.monthly_sales_prediction,
            p.forecast,
            r.incoming_goods,
            r.outgoing_goods,
            r.inventory,
            round(r.remaining_weeks, 1),])

    return response


@login_required
def weekly_summary(request):
    search = request.GET.get('search', '')
    week_input = request.GET.get("week") 
    selected_week_value = ""
    selected_label = None

    records = WeeklyRecord.objects.select_related("product").order_by("-year", "-week_no")

    if search:
        records = records.filter(
            Q(product__product_name__icontains=search) |
            Q(product__jan_code__icontains=search) |
            Q(product__yayoi_code__icontains =search)
        )
    if week_input:
            year, week = str.split(week_input, '-W')
            year = int(year)
            week = int(week)
            records = records.filter(year=year, week_no=week)

            selected_week_value = week_input
            selected_label = iso_week_to_japanese_label(year, week)

    # --- Pagination ---
    paginator = Paginator(records, 50)  # 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate starting index for serial numbers
    start_index = (page_obj.number - 1) * paginator.per_page
    
    context = {
        "records": page_obj,
        "search": search,
        'page_obj': page_obj,
        'start_index': start_index,
        "selected_week_value": selected_week_value,
        "current_year": current_year,
        "current_week": current_week,
        "week_label": week_label,
        "selected_label": selected_label,
    }
    return render(request, 'dashboard/weekly_summary.html', context)

@login_required
def product_list(request):
    search = request.GET.get('search', '')
    products = Product.objects.all()

    if search:
        products = Product.objects.filter(jan_code__icontains=search)
    
     # --- Pagination ---
    paginator = Paginator(products, 20)  # 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/product_list.html', {
        'products': page_obj,  # paginated products
        'page_obj': page_obj,   # pagination info
        'search' : search
    })


@login_required
def inventory_list(request):
    search = request.GET.get('search', '')
    
    # Find the latest weekly record for each product
    latest_records = WeeklyRecord.objects.filter(
        product__jan_code=OuterRef('jan_code')
    ).order_by('-year', '-week_no')

    # Annotate product with latest inventory
    products = Product.objects.annotate(
        year=Subquery(latest_records.values('year')[:1]),
        week_no=Subquery(latest_records.values('week_no')[:1]),
        latest_inventory=Subquery(latest_records.values('inventory')[:1]),
        latest_incoming=Subquery(latest_records.values('incoming_goods')[:1]),
        latest_outgoing=Subquery(latest_records.values('outgoing_goods')[:1]),
        latest_remaining_weeks=Subquery(latest_records.values('remaining_weeks')[:1]),
    ).filter(latest_inventory__gt=0, is_active=True)

    if search:
        products = products.filter(jan_code__icontains=search)
    
        # --- Pagination ---
    paginator = Paginator(products, 20)  # 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Calculate starting index for serial numbers
    start_index = (page_obj.number - 1) * paginator.per_page

    return render(request, 'dashboard/inventory_list.html', {
        'products': page_obj,  # paginated products
        'page_obj': page_obj,   # pagination info
        'search': search,
        'start_index':start_index,
    })

@login_required
def need_attention_list(request):
    search = request.GET.get('search', '')
    export = request.GET.get('export')  # 👈 export flag
    # find latest week with data
    latest_record = WeeklyRecord.objects.order_by('-year', "-week_no").first()
   
    if not latest_record:
        return render(request, 'dashboard/need_attention.html', {'records': []})
     
    records = WeeklyRecord.objects.filter(year=latest_record.year, 
                                          week_no=latest_record.week_no, 
                                          remaining_weeks__lte=5,
                                          product__is_active=True
                                          ).select_related("product")

    if search:
        records = records.filter(Q(product__jan_code__icontains=search) | 
                                 Q(product__product_name__icontains=search)
                                 )
    
     # sort by remaining weeks (highest first)
    records = records.order_by("-remaining_weeks")

    # 🔹 EXPORT MODE (NO PAGINATION)
    if export == "csv":
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="need_attention_{latest_record.year}_W{latest_record.week_no}.csv"'
        )
        response.write('\ufeff')  # BOM for UTF-8

        writer = csv.writer(response)
        writer.writerow([
            '#',
            '商品名',
            'JAN',
            '弥生',
            '残週'
        ])

        for idx, r in enumerate(records, start=1):
            writer.writerow([
                idx,
                r.product.product_name,
                r.product.jan_code,
                r.product.yayoi_code,
                round(r.remaining_weeks, 1)
            ])

        return response
    
    # PAGINATION (20 per page)
    paginator = Paginator(records, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    # Calculate starting index for serial numbers
    start_index = (page_obj.number - 1) * paginator.per_page
    
    return render(request, 'dashboard/need_attention.html', {
        'page_obj': page_obj,
        'search' : search,
        'start_index':start_index,
        'current_year':current_year,
        'current_week':current_week,
        'week_label':week_label,
    })

@login_required
def add_product(request):
    if request.method == "POST":
        jan = request.POST.get("jan_code")
        name = request.POST.get("product_name")
        classification = request.POST.get("classification")
        lead_time = request.POST.get("lead_time")

        try:
            Product.objects.create(
                jan_code=jan,
                product_name=name,
                classification=classification,
                lead_time=lead_time
            )
            messages.success(request, "Product added successfully!")
            return redirect("dashboard-products")
        except Exception as e:
            messages.error(request, "Error adding product.")

    return render(request, "dashboard/add_product.html")