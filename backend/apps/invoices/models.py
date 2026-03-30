import uuid

from django.db import models


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=96, unique=True, db_index=True)
    file = models.FileField(upload_to="invoices/%Y/%m/", blank=True)
    file_size = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} ({self.order.order_number})"
