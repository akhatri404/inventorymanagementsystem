from django.urls import path
from . import views

urlpatterns = [
    path('', views.weekly_list, name='weekly_list'),
    path('add/', views.add_weekly_record, name='add_weekly_record'),
    path('bulk-add/', views.add_weekly_bulk, name='weekly_bulk_add'),
    path("upload-inventory/", views.upload_weekly_inventory, name="upload_weekly_inventory"),
    path("upload-historical/", views.upload_historical_weekly, name="upload_historical_weekly"),
]
