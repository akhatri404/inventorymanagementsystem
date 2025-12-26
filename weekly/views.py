from django.shortcuts import render, redirect,  get_object_or_404
from .models import WeeklyRecord, FutureIncomingPlan, WeeklyInventory
from .forms import WeeklyRecordForm
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from datetime import date
from django.contrib import messages
from products.models import Product, ProductMaster
from django.utils import timezone
from django.db import transaction
import pandas as pd
from django.http import JsonResponse
from django.db.models import Q
from dashboard.views import iso_week_to_japanese_label
from django.core.paginator import Paginator

def iso_week_to_japanese_label(iso_year: int, iso_week: int) -> str:
    # Monday of ISO week
    monday = date.fromisocalendar(iso_year, iso_week, 1)

    # Sunday-start week (Japanese UI)
    sunday = monday
    return f"{sunday.strftime('%y')}年{sunday.month}月{sunday.day}日週"

today = timezone.now().date()
current_year, current_week, _ = today.isocalendar()
week_label = iso_week_to_japanese_label(current_year, current_week)

@login_required
@role_required(['add'])
def add_weekly_record(request):
    today = date.today()
    current_year = today.isocalendar().year
    current_week = today.isocalendar().week

    if request.method == 'POST':
        form = WeeklyRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.save()
            return redirect('weekly_list')

    else:
        form = WeeklyRecordForm(initial={
            'year': int(request.POST.get("year", current_year)),
            'week_no': int(request.POST.get("week", current_week))
        })

    return render(request, 'weekly/add_weekly.html', {'form': form})

@login_required
@role_required(['view'])
def weekly_list(request):
    records = WeeklyRecord.objects.all().order_by('-year', '-week_no')
    return render(request,'weekly/weekly_list.html',{'records':records})

def to_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


@login_required
@role_required(['add'])
def add_weekly_bulk(request):
    # Compute previous week automatically
    def get_previous_week():
        today = date.today()
        last_week = today #- timedelta(days=7)
        y, w, _ = last_week.isocalendar()
        return y, w

    default_year, default_week = get_previous_week()
    week_label = iso_week_to_japanese_label(default_year, default_week)

    products = Product.objects.all().order_by("yayoi_code")

    if request.method == "POST":
        # Get user-selected year/week (fallback to current)
        year = int(request.POST.get("year", default_year))
        week = int(request.POST.get("week", default_week))

        selected = request.POST.getlist("selected_products")
        created_any = False
        updated_any = False

        for pid in selected:
            product = Product.objects.get(id=pid)

            # 🔹 Future plan fallback
            planned_incoming = get_default_incoming(product, year, week)
            incoming = to_int(request.POST.get(f"incoming_{pid}", "").strip() or planned_incoming)
            inventory = to_int(request.POST.get(f"inventory_{pid}", 0))
            
            # Get the product to ensure we process in correct order
            product = Product.objects.get(id=pid)
            
            record, created = WeeklyRecord.objects.update_or_create(
                product=product,
                year=year,
                week_no=week,
                defaults={
                    'incoming_goods': incoming,
                    'inventory': inventory,
                }
            )
            
            record.save()  # ensure save() calculations run
            created_any |= created
            updated_any |= not created
            FutureIncomingPlan.objects.filter(product=product, year=year, week_no=week).delete()

        if created_any and updated_any:
            messages.success(request, "Weekly records added and updated successfully!")
        elif created_any:
            messages.success(request, "Weekly records added successfully!")
        else:
            messages.success(request, "Weekly records updated successfully!")
               
        return redirect("weekly-summary")

    # For initial GET load:
    return render(request, "weekly/add_weekly_bulk.html", {
        "products": products,
        "year": default_year,
        "week": default_week,
        "week_label": week_label,
    })

# @login_required
# def upload_weekly_inventory(request):
#     if request.method != "POST":
#         return JsonResponse({"error": "POST only"}, status=400)

#     file = request.FILES.get("file")
#     if not file:
#         return JsonResponse({"error": "No file uploaded"}, status=400)

#     try:
#         df = pd.read_excel(file, sheet_name='Sheet1')
#     except:
#         return JsonResponse({"error": "Invalid Excel file"}, status=400)

#     required = {"yayoi_code", "product_name", "inventory"}
#     if not required.issubset(df.columns):
#         return JsonResponse({
#             "error": "Excel must include: yayoi_code, product_name, inventory"
#         }, status=400)

#     # Convert excel data into dict: yayoi_code → inventory
#     excel_inventory = {}
#     for _, row in df.iterrows():
#         code = str(row["yayoi_code"]).strip()
#         inv = row["inventory"]
#         excel_inventory[code] = inv

#     # Prepare final result including ALL products
#     result = {}
#     all_products = Product.objects.all()

#     for p in all_products:
#         # If yayoi_code exists in Excel → use it
#         if p.yayoi_code in excel_inventory:
#             result[p.id] = excel_inventory[p.yayoi_code]
#         else:
#             result[p.id] = 0   # Default if missing

#     return JsonResponse({"data": result})

@login_required
@role_required(['add'])
def upload_product_master(request):
    message = ""
    
    if request.method == "POST":
        file = request.FILES.get("file")
        file_ext = file.name.split('.')[-1].lower()
        if not file:
            message = "No file uploaded"
        else:
            try:
                if file_ext == 'xls':
                    df = pd.read_excel(file, header=3, engine='xlrd')  # for old .xls files
                elif file_ext == 'xlsx':
                    df = pd.read_excel(file, header=3, engine='openpyxl')  # for .xlsx files
                else:
                    raise ValueError("Unsupported file type")
            except Exception:
                message = "Invalid Excel file"
            else:
                required_columns = {"商品コード", "商品名", "入り数"}
                if not required_columns.issubset(df.columns):
                    message = "Missing required columns"
                else:
                    created, updated = 0, 0
                    for _, row in df.iterrows():
                        obj, is_created = ProductMaster.objects.update_or_create(
                            yayoi_code=row["商品コード"],
                            defaults={"product_name": row["商品名"], "quantity": row["入り数"]},
                        )
                        created += int(is_created)
                        updated += int(not is_created)
                    message = f"{created} products created, {updated} updated"

    # For GET request or after processing POST, render the same template
    return render(request, "weekly/upload_product_master.html", {
        "message": message
    })

@login_required
@role_required(['add'])
def weekly_inventory_table(request):
    today = date.today()
    year, week_no, _ = today.isocalendar()
    search = request.GET.get("search", "")
    if request.method == "GET":
        week_value = request.GET.get("week")
        
        if week_value:
            year_str, week_str = week_value.split('-W')
            year = int(year_str)
            week_no = int(week_str)

    if search:
        products = ProductMaster.objects.filter(
            Q(product_name__icontains=search) |
            Q(yayoi_code__icontains=search)
        ).order_by("yayoi_code")
    else:
        products = ProductMaster.objects.all().order_by("yayoi_code")

    # Fetch existing WeeklyInventory for this week
    existing_inventory = {
        i.product_id: i
        for i in WeeklyInventory.objects.filter(year=year, week_no=week_no)
    }

    rows = []
    for product in products:
        inv = existing_inventory.get(product.id)
        rows.append({
            "product_id": product.id,
            "yayoi_code": product.yayoi_code,
            "product_name": product.product_name,
            #"sn": getattr(product, "sn", ""),  # if sn exists in ProductMaster
            "quantity": product.quantity,
            "total_quantity": inv.total_quantity if inv else "",
            "no_of_cases": inv.no_of_cases if inv else "",
            "loose": inv.loose if inv else "",
        })

    return render(request, "weekly/weekly_inventory_form.html", {
        "rows": rows,
        "year": year,
        "week_no": week_no,
        "search": search,
    })

@transaction.atomic
def save_weekly_inventory_table(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    year = request.POST.get("year")
    week_no = request.POST.get("week_no")

    for key in request.POST:
        if key.startswith("quantity_"):
            product_id = key.replace("quantity_", "")
            quantity = int(request.POST.get(f"quantity_{product_id}", 0))
            total = int(request.POST.get(f"total_{product_id}", 0))

            if quantity > 0:
                no_of_cases = total // quantity
                loose = total % quantity
            else:
                no_of_cases = 0
                loose = 0

            WeeklyInventory.objects.update_or_create(
                product_id=product_id,
                year=year,
                week_no=week_no,
                defaults={
                    "quantity": quantity,
                    "total_quantity": total,
                    "no_of_cases": no_of_cases,
                    "loose": loose,
                },
            )

    return JsonResponse({"message": "Weekly inventory saved"})

# -------------------------
# Data3 cross sheet mapping
# -------------------------
DATA3_MAP = {
    "02-99-0059": "02-52-0001",
    "02-99-0060": "02-52-0002",
    "02-99-0061": "02-52-0003",
    "02-99-0062": "02-52-0004",
    "02-99-0063": "02-52-0005",
    "02-99-0064": "02-52-0006",
    "02-99-0065": "02-52-0007",
    "02-99-0066": "02-52-0008",
    "02-99-0067": "02-52-0009",
    "02-99-0068": "02-52-0010",
    "02-99-0069": "02-52-0011",
    "02-99-0070": "02-52-0012",
}

# -------------------------
# E column category values
# -------------------------
CATEGORY_MAP = {
    "02-52-0001": 25, "02-52-0002": 15, "02-52-0003": 8,
    "02-52-0004": 5,  "02-52-0005": 3,  "02-52-0006": 25,
    "02-52-0007": 25, "02-52-0008": 15, "02-52-0009": 8,
    "02-52-0010": 5,  "02-52-0011": 3,  "02-52-0012": 25
}


#---------------------------------------------------------
def load_weekly_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    inventory = WeeklyInventory.objects.filter(
        year=current_year, week_no=current_week
    ).select_related("product")

    data = [
        {
            "yayoi_code": i.product.yayoi_code,
            "product_name": i.product.product_name,
            "quantity": i.quantity,
            "total_quantity": i.total_quantity,
            "no_of_cases": i.no_of_cases,
            "lose": i.loose,
        }
        for i in inventory
    ]

    return JsonResponse({"data": data})
#---------------------------------------------------------

# ======================================================================
# MAIN FUNCTION — handles upload & returns computed final D values
# ======================================================================
@login_required
@role_required(['add'])
def upload_weekly_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    file = request.FILES.get("file")
    file_ext = file.name.split('.')[-1].lower()
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    try:
        if file_ext == 'xls':
            df = pd.read_excel(file, header=3, engine='xlrd')  # for old .xls files
        elif file_ext == 'xlsx':
            df = pd.read_excel(file, header=3, engine='openpyxl')  # for .xlsx files
    except:
        return JsonResponse({"error": "Invalid Excel file"}, status=400)

    required = {"商品コード", "商品名", "総数"} 
    if not required.issubset(df.columns):
        return JsonResponse({
            "error": "Excel must include: 商品コード, 商品名, 総数"
        }, status=400)

    # -------------------------
    # Extract values
    # -------------------------
    codes = df["商品コード"].astype(str).tolist()
    names = df["商品名"].astype(str).tolist()
    c_values = df["総数"].fillna(0).astype(int).tolist()

    # -------------------------
    # E column
    # -------------------------
    e_values = [CATEGORY_MAP.get(code, 0) for code in codes]

    # -------------------------
    # H column (string detection)
    # -------------------------
    h_values = []
    count_c, count_d1, count_d3 = 0, 0, 0

    for name in names:
        if "ねこちゃんにもやさしいみるく2" in name:
            count_c += 1
            h_values.append(f"C1_{count_c}")
        elif "わんちゃんにもやさしいみるく300ml 3" in name:
            count_d1 += 1
            h_values.append(f"D1_{count_d1}")
        elif "わんちゃんにもやさしいみるく3個" in name:
            count_d3 += 1
            h_values.append(f"D3_{count_d3}")
        else:
            h_values.append(None)

    # -------------------------
    # I column — SUM based on H group
    # -------------------------
    i_values = []
    for h in h_values:
        if not h:
            i_values.append(0)
            continue

        prefix = h[0]  # "C" or "D"
        total = 0

        for h2, c in zip(h_values, c_values):
            if not h2 or not h2.startswith(prefix):
                continue

            if h2.startswith("D3"):
                total += c * 3
            else:
                total += c

        i_values.append(total)

    # -------------------------
    # D preliminary = IF(I > 0, I, C)
    # -------------------------
    d_pre = [
        i if i > 0 else c
        for i, c in zip(i_values, c_values)
    ]

    # -------------------------
    # F = D_pre * E
    # -------------------------
    f_values = [d * e for d, e in zip(d_pre, e_values)]

    # -------------------------
    # G column: Data3 cross-reference
    # -------------------------
    f_lookup = dict(zip(codes, f_values))
    g_values = []

    for code in codes:
        if code in DATA3_MAP:
            linked = DATA3_MAP[code]
            g_values.append(f_lookup.get(linked, 0))
        else:
            g_values.append(0)

    # -------------------------
    # FINAL D = IF(I > 0, I, C + G)
    # -------------------------
    final_d = [
        i if i > 0 else (c + g)
        for i, c, g in zip(i_values, c_values, g_values)
    ]

    # -------------------------
    # Prepare JSON output for frontend inputs
    # -------------------------
    result = {}
    all_products = Product.objects.all()

    for p in all_products:
        if p.yayoi_code in codes:
            idx = codes.index(p.yayoi_code)
            result[p.id] = final_d[idx]
        else:
            result[p.id] = 0

    return JsonResponse({"data": result})

@login_required
def upload_historical_weekly(request):
    context = {}
    if request.method == "POST":
        year = int(request.POST.get("year"))
        week = int(request.POST.get("week_no"))
        file = request.FILES.get("file")

        context["year"] = year
        context["week_no"] = week        

        if not file:
            messages.error(request, "No file uploaded")
            return redirect("upload_historical_weekly")

        try:
            df = pd.read_excel(file)
        except:
            messages.error(request, "Invalid Excel file")
            return redirect("upload_historical_weekly")

        required = {"yayoi_code", "incoming", "outgoing", "inventory"}
        if not required.issubset(df.columns):
            messages.error(
                request,
                "Excel must contain: yayoi_code, incoming, outgoing, inventory"
            )
            return redirect("upload_historical_weekly")

        missing_products = []
        imported = 0
        numeric_cols = ["incoming", "outgoing", "inventory"]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        df = df.fillna(0)

        for _, row in df.iterrows():
            code = str(row["yayoi_code"]).strip()

            try:
                product = Product.objects.get(yayoi_code=code)
            except Product.DoesNotExist:
                missing_products.append(code)
                continue

            WeeklyRecord.objects.update_or_create(
                product=product,
                year=year,
                week_no=week,
                defaults={
                    "incoming_goods": int(row["incoming"] or 0),
                    "outgoing_goods": int(row["outgoing"] or 0),
                    "inventory": int(row["inventory"] or 0),
                    "is_historical": True
                }
            )
            imported += 1

        if missing_products:
            messages.warning(
                request,
                f"{len(missing_products)} products not found and skipped."
            )

        messages.success(
            request,
            f"Historical data uploaded for Year {year}, Week {week}. ({imported} records)"
        )

    return render(request, "weekly/upload_historical.html", context)


def future_incoming_view(request):
    search = request.GET.get('search')
    week_value = request.GET.get('week') or request.POST.get('week')

    year = week = None
    if week_value:
        year_str, week_str = week_value.split('-W')
        year = int(year_str)
        week = int(week_str)

        # ✅ Normalize to ISO week/year
        iso_date = date.fromisocalendar(year, week, 1)
        year, week, _ = iso_date.isocalendar()

    products = Product.objects.filter(is_active=True).order_by("yayoi_code")

    # Filter for display only
    if search:
        products = products.filter(
            Q(product_name__icontains=search) |
            Q(yayoi_code__icontains=search)
        )

    if request.method == 'POST':
        if not week_value:
            messages.error(request, "Week value is required")
            return redirect(request.path)

        # ✅ Always save for ALL active products
        save_products = Product.objects.filter(is_active=True)

        for product in save_products:
            value = request.POST.get(f'incoming_{product.id}')

            if value is None:
                continue  # field not submitted at all

            planned_value = int(value)

            if planned_value > 0:
                FutureIncomingPlan.objects.update_or_create(
                    product=product,
                    year=year,
                    week_no=week,
                    defaults={'planned_incoming': planned_value}
                )
            else:
                # Optional: remove existing record if user cleared it
                FutureIncomingPlan.objects.filter(
                    product=product,
                    year=year,
                    week_no=week
                ).delete()

        messages.success(
            request, f"Future incoming stock saved for {year} W{week}"
        )
        return redirect(f"{request.path}")

    plans = {
        p.product_id: p.planned_incoming
        for p in FutureIncomingPlan.objects.filter(year=year, week_no=week)
    }

    return render(request, 'weekly/future_incoming.html', {
        'products': products,
        'plans': plans,
        'search': search,
    })


def get_default_incoming(product, year, week):
    plan = FutureIncomingPlan.objects.filter(
        product=product,
        year=year,
        week_no=week
    ).first()

    return plan.planned_incoming if plan else 0

def all_future_incoming_view(request):
    search = request.GET.get("search", "")
    weekvalue = request.GET.get("week")

    plans = FutureIncomingPlan.objects.select_related("product").filter(
        product__is_active=True,
        planned_incoming__gt=0
    )

    if search:
        plans = plans.filter(
            Q(product__product_name__icontains=search) |
            Q(product__yayoi_code__icontains=search)
        )

    if weekvalue and "-W" in weekvalue:
        try:
            year_str, week_str = weekvalue.split("-W")
            year = int(year_str)
            week = int(week_str)
            plans = plans.filter(year=year, week_no=week)
        except ValueError:
            pass

    # Default behavior → future only
    if not search and not weekvalue:
        plans = plans.filter(
            Q(year__gt=current_year) |
            (Q(year=current_year) & Q(week_no__gte=current_week))
        )

    plans = plans.order_by("year", "week_no", "product__yayoi_code")

    paginator = Paginator(plans, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    start_index = (page_obj.number - 1) * paginator.per_page

    return render(request, "weekly/all_future_incoming.html", {
        "page_obj": page_obj,
        "search": search,
        "start_index": start_index,
        "current_year": current_year,
        "current_week": current_week,
    })
