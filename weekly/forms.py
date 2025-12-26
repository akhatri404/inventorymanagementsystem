from django import forms
from .models import WeeklyRecord, WeeklyInventory
from products.models import Product
from datetime import date
from django_select2.forms import ModelSelect2Widget

class ProductWidget(ModelSelect2Widget):
    model = Product
    search_fields = [
        "jan_code__icontains",
        "product_name__icontains",
    ]
    
    def label_from_instance(self, obj):
        return f"{obj.jan_code} - {obj.product_name}"

class WeeklyRecordForm(forms.ModelForm):
    class Meta:
        model = WeeklyRecord
        fields = ["year", "week_no", "product", "incoming_goods", "outgoing_goods"]
        widgets = {
                    "year": forms.NumberInput(attrs={"class": "form-control"}),
                    "week_no": forms.NumberInput(attrs={"class": "form-control"}),
                    "product": ProductWidget(attrs={"class": "form-control"}),
                    "incoming_goods": forms.NumberInput(attrs={"class": "form-control"}),
                    "outgoing_goods": forms.NumberInput(attrs={"class": "form-control"}),
                }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["incoming_goods"].initial = None
        self.fields["outgoing_goods"].initial = None

        # Show "JAN - Product Name"
        self.fields["product"].label_from_instance = (
            lambda obj: f"{obj.jan_code} - {obj.product_name}"
        )

class WeeklyInventoryForm(forms.ModelForm):
    class Meta:
        model = WeeklyInventory
        fields = ["year", "week_no", "product", "total_quantity"]
        widgets = {
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "week_no": forms.NumberInput(attrs={"class": "form-control"}),
            "product": ProductWidget(attrs={"class": "form-control"}),
        }