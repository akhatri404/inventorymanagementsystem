from django.db import models

class Product(models.Model):
    CLASS_CHOICES = (('国外','国外'),('国内','国内'))
    LEAD_CHOICES = (('45','45'),('60','60'),('45～60','45～60'))

    classification = models.CharField(max_length=10, choices=CLASS_CHOICES, null=True, blank=True)
    lead_time = models.CharField(max_length=10, choices=LEAD_CHOICES, null=True, blank=True)
    ordering = models.IntegerField(null=True, blank=True)
    yayoi_code = models.CharField(max_length=50, unique=True, null=False, blank=False)
    jan_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    product_name = models.CharField(max_length=200, null=False, blank=False)
    handling = models.CharField(max_length=200, blank=True, null=True)
    specifications = models.CharField(max_length=200, blank=True ,null=True)
    monthly_sales_prediction = models.FloatField(default=0, null=True, blank=True)
    forecast = models.FloatField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.yayoi_code} | {self.product_name}"

    def save(self, *args, **kwargs):
        self.forecast = (self.monthly_sales_prediction / 30) * 7
        super().save(*args, **kwargs)

class ProductDefaults(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE)
    default_incoming = models.IntegerField(default=0)
    default_outgoing = models.IntegerField(default=0)

    def __str__(self):
        return f"Defaults for {self.product.product_name}"

class ProductMaster(models.Model):
    yayoi_code = models.CharField(max_length=50, unique=True)
    product_name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.yayoi_code} - {self.product_name}"