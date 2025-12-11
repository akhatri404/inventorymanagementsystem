from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Product, ProductDefaults
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from weekly.models import WeeklyRecord
from django.utils import timezone

@login_required
@role_required(['add'])
def product_default_settings(request):
    # Ensure every product has defaults
    for p in Product.objects.all():
        ProductDefaults.objects.get_or_create(product=p)

    defaults = ProductDefaults.objects.select_related("product").all()

    if request.method == "POST":
        for d in defaults:
            outgoing = request.POST.get(f"default_outgoing_{d.product.id}", 0)

            d.default_outgoing = int(outgoing or 0)
            d.save()

        messages.success(request, "Default values updated successfully!")
        return redirect("product_default_settings")

    return render(request, "products/default_settings.html", {
        "defaults": defaults
    })

@login_required
@role_required(['add'])
def get_product_defaults(request):
    products = Product.objects.all()
    data = {}

    for p in products:
        d = getattr(p, "productdefaults", None)
        data[p.id] = {
            "outgoing": d.default_outgoing if d else 0,
        }

    return JsonResponse(data)
