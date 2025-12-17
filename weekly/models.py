from django.db import models
from products.models import Product, ProductDefaults
from django.conf import settings
from datetime import date

class WeeklyRecord(models.Model):
    year = models.IntegerField()
    week_no = models.IntegerField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    incoming_goods = models.IntegerField(default=0)
    outgoing_goods = models.IntegerField(default=0)
    inventory = models.IntegerField(default=0)
    remaining_weeks = models.FloatField(default=0)
    is_historical = models.BooleanField(default=False)  # 👈 NEW
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('year', 'week_no', 'product')
        ordering = ['-year', '-week_no', 'product__jan_code']

    def save(self, *args, **kwargs):    # 🚨 Historical data → NEVER recalculate
        if self.is_historical:
            super().save(*args, **kwargs)
            return

        # --- 1. Determine previous year & week correctly ---
        if self.week_no > 1:
            prev_year = self.year
            prev_week = self.week_no - 1
        else:
            # Week 1 → look up last ISO week of previous year
            prev_year = self.year - 1
            prev_week = date(prev_year, 12, 28).isocalendar()[1]

        # --- 2. Query the actual previous weekly record ---
        try:
            prev_record = WeeklyRecord.objects.get(
                product=self.product,
                year=prev_year,
                week_no=prev_week
            )
        except WeeklyRecord.DoesNotExist:
            prev_record = None

        # --- 3. Compute outgoing correctly ---
        if prev_record:
            # outgoing = previous_inventory + incoming - current_inventory
            self.outgoing_goods = abs(
                (prev_record.inventory or 0)
                + (self.incoming_goods or 0)
                - (self.inventory or 0)
            )
        else:
            # First-ever record → fallback to product default
            try:
                default = ProductDefaults.objects.get(product=self.product)
                self.outgoing_goods = default.default_outgoing
            except ProductDefaults.DoesNotExist:
                self.outgoing_goods = 0

        # --- 4. Remaining weeks calculation ---
        if self.product.forecast > 0:
            self.remaining_weeks = (self.inventory or 0) / self.product.forecast
        else:
            self.remaining_weeks = 0

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.product.jan_code} | {self.product.product_name} — Y{self.year} W{self.week_no}"

