from django.shortcuts import render, redirect,  get_object_or_404
from .models import WeeklyRecord
from .forms import WeeklyRecordForm
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from datetime import date, timedelta
from django.contrib import messages
from products.models import Product

import pandas as pd
from django.http import JsonResponse

from dashboard.views import iso_week_to_japanese_label

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

        for pid in selected:
            incoming = to_int(request.POST.get(f"incoming_{pid}", 0))
            inventory = to_int(request.POST.get(f"inventory_{pid}", 0))
            
            # Get the product to ensure we process in correct order
            product = Product.objects.get(id=pid)
            
            record, created = WeeklyRecord.objects.get_or_create(
                product=product,
                year=year,
                week_no=week,
                defaults={
                    'incoming_goods': incoming,
                    'inventory': inventory,
                }
            )

            record.save()  # ensure save() calculations run

        if created:
            messages.success(request, "Weekly record added successfully!")
        else:
            messages.warning(request, f"Weekly record for week {week} already exists!")
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


# ======================================================================
# MAIN FUNCTION — handles upload & returns computed final D values
# ======================================================================
@login_required
@role_required(['add'])
def upload_weekly_inventory(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    try:
        df = pd.read_excel(file)
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
    if request.method != "POST":
        return render(request, "weekly/upload_historical.html")

    year = int(request.POST.get("year"))
    week = int(request.POST.get("week_no"))
    file = request.FILES.get("file")

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

    return redirect("weekly-summary")
