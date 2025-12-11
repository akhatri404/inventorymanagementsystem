from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='dashboard-home'),
    path('export_csv/', views.export_csv, name='export_csv'),
    path('weekly-summary/', views.weekly_summary, name='weekly-summary'),
    path('products/', views.product_list, name='dashboard-products'),
    path('inventory/', views.inventory_list, name='dashboard-inventory'),
    path('need-attention/', views.need_attention_list, name='dashboard-need-attention'),
   ]
