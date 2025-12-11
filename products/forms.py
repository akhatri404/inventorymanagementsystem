from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'classification': forms.Select(attrs={'class': 'form-select'}),
            'lead_time': forms.Select(attrs={'class': 'form-select'}),
            'ordering': forms.NumberInput(attrs={'class': 'form-control'}),
            'yayoi_code': forms.TextInput(attrs={'class': 'form-control'}),
            'jan_code': forms.TextInput(attrs={'class': 'form-control'}),
            'product_name': forms.TextInput(attrs={'class': 'form-control'}),
            'handling': forms.TextInput(attrs={'class': 'form-control'}),
            'specifications': forms.TextInput(attrs={'class': 'form-control'}),
            'monthly_sales_prediction': forms.NumberInput(attrs={'class': 'form-control'}),
        }
