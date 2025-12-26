from django.urls import path
from . import views

urlpatterns = [
    path('', views.weekly_list, name='weekly_list'),
    path('add/', views.add_weekly_record, name='add_weekly_record'),
    path('bulk-add/', views.add_weekly_bulk, name='weekly_bulk_add'),
    path("upload-inventory/", views.upload_weekly_inventory, name="upload_weekly_inventory"),
    path("upload-historical/", views.upload_historical_weekly, name="upload_historical_weekly"),
    path('future-incoming/', views.future_incoming_view, name='future_incoming'),
    path('future-incoming/all/', views.all_future_incoming_view, name='all_future_incoming'),
    path('weekly-inventory/', views.weekly_inventory_table, name="weekly_inventory_form"),
    path("save/", views.save_weekly_inventory_table, name="save_weekly_inventory_table"),
    path("upload-product-master/", views.upload_product_master, name="upload_product_master"),

]
