from django.urls import path
from . import views
from .views_defaults import product_default_settings, get_product_defaults

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.add_product, name='add_product'),
    path('update/<str:yayoi_code>/', views.update_product, name='update_product'),
    path('delete/<str:yayoi_code>/', views.delete_product, name='delete_product'),
    path("defaults/", product_default_settings, name="product_default_settings"),
    path("defaults/load/", get_product_defaults, name="get_product_defaults"),
    path("upload-products/", views.upload_products, name="upload_products"),
    path("upload-yayoi/", views.upload_yayoi_codes, name="upload_yayoi_codes"),
    path('toggle-status/<str:yayoi_code>/', views.toggle_product_status, name='toggle_product_status'),
    ]
