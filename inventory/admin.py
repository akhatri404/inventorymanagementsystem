from django.contrib import admin
from accounts.models import CustomUser
from products.models import Product, ProductMaster
from weekly.models import WeeklyRecord, WeeklyInventory, FutureIncomingPlan 

admin.site.register(CustomUser)
admin.site.register(Product)
admin.site.register(WeeklyRecord)
admin.site.register(WeeklyInventory)
admin.site.register(ProductMaster)
admin.site.register(FutureIncomingPlan)
