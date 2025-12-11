from django.contrib import admin
from accounts.models import CustomUser
from products.models import Product
from weekly.models import WeeklyRecord 

admin.site.register(CustomUser)
admin.site.register(Product)
admin.site.register(WeeklyRecord)