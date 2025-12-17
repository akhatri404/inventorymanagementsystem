from django.shortcuts import render, redirect, get_object_or_404
from .models import Product
from .forms import ProductForm
from accounts.decorators import role_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date

import pandas as pd
from django.contrib import messages

from dashboard.views import iso_week_to_japanese_label
today = date.today()
current_year = today.isocalendar().year
current_week = today.isocalendar().week
week_label = iso_week_to_japanese_label(current_year, current_week)

@login_required
@role_required(['add'])
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request,'products/add_product.html',{'form':form})

@login_required
@role_required(['update'])
def update_product(request, yayoi_code):
    product = get_object_or_404(Product, yayoi_code=yayoi_code)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request,'products/update_product.html',{'form':form})

@login_required
@role_required(['view'])
def product_list(request):
    search = request.GET.get('search', '')

    status_filter = request.GET.get("status", 'all')   # active / inactive / None

    if status_filter == "active":
        products = Product.objects.filter(is_active=True)
    elif status_filter == "inactive":
        products = Product.objects.filter(is_active=False)
    else:
        products = Product.objects.all()

    if search:
        products = products.filter(Q(jan_code__icontains=search) | 
                                   Q(yayoi_code__icontains=search) |
                                   Q(product_name__icontains=search)
        )

         # --- Pagination ---
    paginator = Paginator(products, 50)  # 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    start_index = (page_obj.number - 1) * paginator.per_page
    
    return render(request, 'products/product_list.html', {
        'products': page_obj,  # paginated products
        'page_obj': page_obj,   # pagination info
        'search': search,
        'status_filter': status_filter,
        'start_index': start_index,
        'current_year':current_year,
        'current_week':current_week,
        'week_label':week_label,
        })

@login_required
@role_required(['delete'])
def delete_product(request, yayoi_code):
    product = get_object_or_404(Product, yayoi_code=yayoi_code)
    if request.method == 'POST':
        product.delete()
        return redirect('product_list')
    return render(request, 'products/delete_confirm.html', {'product': product})


@login_required
def upload_products(request):
    if request.method == "POST":
        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Please upload an Excel file.")
            return redirect("upload_products")

        try:
            df = pd.read_excel(file)

            required_columns = ["classification", "lead_time", "ordering", "yayoi_code", "jan_code", 
                                "product_name", "handling", "specifications", "monthly_sales_prediction"]
            for col in required_columns:
                if col not in df.columns:
                    messages.error(request, f"Missing column: {col}")
                    return redirect("upload_products")

            created_count = 0
            updated_count = 0

            for _, row in df.iterrows():
                yayoi = str(row["yayoi_code"]).strip()

                def clean_value(value):
                    if pd.isna(value):
                        return None
                    return value

                jan_raw = row.get("jan_code")

                # convert to string safely
                if pd.isna(jan_raw):
                    jan = None
                else:
                    jan = str(jan_raw).replace(".0", "").strip()
                    # Fix scientific notation
                    if "e" in jan.lower():
                        jan = "{:.0f}".format(float(jan_raw))

                product, created = Product.objects.update_or_create(
                    yayoi_code = yayoi,
                    jan_code=jan,
                    defaults={
                        "classification": clean_value(row.get("classification")),
                        "lead_time": clean_value(row.get("lead_time")),
                        "ordering": clean_value(row.get("ordering")),
                        "product_name": row.get("product_name"),
                        "handling": clean_value(row.get("handling")),
                        "specifications": clean_value(row.get("specifications")),
                        "monthly_sales_prediction": clean_value(row.get("monthly_sales_prediction")) or 0,
                    }
                )


                if created:
                    created_count += 1
                else:
                    updated_count += 1

            messages.success(request, f"Upload complete! Created: {created_count}, Updated: {updated_count}")

        except Exception as e:
            messages.error(request, f"Error reading file: {e}")

        return redirect("upload_products")

    return render(request, "products/upload_products.html")


@login_required
def upload_yayoi_codes(request):

    # restrict to admin
    if not request.user.is_staff:
        return HttpResponseForbidden("You are not allowed to access this page.")

    if request.method == "POST":
        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Please upload a file.")
            return redirect("upload_yayoi_codes")

        try:
            df = pd.read_excel(file)
        except:
            messages.error(request, "Invalid Excel file format.")
            return redirect("upload_yayoi_codes")

        # Check required columns
        required_columns = {"product_name", "yayoi_code"}
        if not required_columns.issubset(df.columns):
            messages.error(request, "Missing required columns: product_name, yayoi_code")
            return redirect("upload_yayoi_codes")

        updated = 0
        not_found = []

        for _, row in df.iterrows():
            pname = str(row["product_name"]).strip()
            new_yayoi = str(row["yayoi_code"]).strip()

            try:
                product = Product.objects.get(product_name=pname)
                product.yayoi_code = new_yayoi
                product.save()
                updated += 1
            except Product.DoesNotExist:
                not_found.append(pname)

        messages.success(request, f"Updated Yayoi codes for {updated} products.")

        if not_found:
            messages.warning(request, f"Products not found: {', '.join(not_found)}")

        return redirect("upload_yayoi_codes")

    return render(request, "products/upload_yayoi_codes.html")


def toggle_product_status(request, yayoi_code):
    product = get_object_or_404(Product, yayoi_code=yayoi_code)
    product.is_active = not product.is_active
    product.save()
    status = "active" if product.is_active else "inactive"
    messages.success(request, f"{product.product_name} is now {status}.")
    
    # redirect back to the same page, including ?search=xxx
    return redirect(request.META.get('HTTP_REFERER', 'product_list'))