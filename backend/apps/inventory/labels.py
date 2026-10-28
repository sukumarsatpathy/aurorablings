"""
Label sheet — the file the label printer app prints barcode stickers from.

    POST /api/v1/inventory/labels/
         {items: [{variant_id, copies}], format?: "xlsx" | "csv"}

Returns a spreadsheet with ONE ROW PER STICKER (a line with copies=3 becomes
three identical rows), because label apps such as WE PRINT print one label per
row and have no notion of a "copies" column. Columns:

    Barcode | Name | SKU | MRP

Barcode is the variant's label number, sent as text so Excel doesn't turn it
into 1.00E+07. Name is the short label name (≤ 20 chars). MRP is the variant's
regular price — not a live offer price, because a sticker outlives an offer.
Whatever is printed, the till still charges the price in the database.

Printing labels never changes stock. Stock is added by receiving it (single or
bulk receive); this endpoint only reads.

Kept in its own module so the main inventory views/services stay untouched.
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.catalog.models import ProductVariant
from core.exceptions import ValidationError

MAX_COPIES_PER_LINE = 1_000
MAX_LABELS = 5_000
MAX_LINES = 500

HEADERS = ["Barcode", "Name", "SKU", "MRP"]


def _mrp(price: Decimal) -> str:
    """499.00 → "499", 499.50 → "499.50"."""
    if price is None:
        return ""
    return str(int(price)) if price == price.to_integral_value() else f"{price:.2f}"


def label_rows(items) -> list[list[str]]:
    """
    `items` = [{"variant_id", "copies"}] → one row per sticker, in the order
    given. Lines for the same variant are added together.
    """
    merged: "OrderedDict[str, int]" = OrderedDict()
    for item in items:
        vid = str(item["variant_id"])
        merged[vid] = merged.get(vid, 0) + int(item["copies"])
    if not merged:
        raise ValidationError("Choose at least one item to print.")

    total = sum(merged.values())
    if total > MAX_LABELS:
        raise ValidationError(f"Up to {MAX_LABELS} labels per file — this asks for {total}. Print in smaller batches.")

    variants = {
        str(v.pk): v
        for v in ProductVariant.objects.select_related("product")
        .prefetch_related("attribute_values__attribute")
        .filter(pk__in=list(merged), product__deleted_at__isnull=True)
    }
    missing = [vid for vid in merged if vid not in variants]
    if missing:
        raise ValidationError(
            f"{len(missing)} item{'s' if len(missing) != 1 else ''} no longer exist. Reload the page and try again."
        )

    rows: list[list[str]] = []
    for vid, copies in merged.items():
        v = variants[vid]
        if not v.barcode:  # only possible for rows created by bulk_create
            v.save(update_fields=["barcode"])
        row = [v.barcode, v.label_text, v.sku, _mrp(v.price)]
        rows.extend([row] * copies)
    return rows


def _csv(rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    writer.writerows(rows)
    # BOM so Excel on Windows opens it as UTF-8.
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _xlsx(rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Labels"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    # Text format on the Barcode and SKU columns: an 8-digit number left as a
    # number displays as 1.00E+07 in some apps and loses meaning.
    for col in ("A", "C"):
        for cell in ws[col]:
            cell.number_format = "@"
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 8
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ─────────────────────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────────────────────

class LabelItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    copies = serializers.IntegerField(min_value=1, max_value=MAX_COPIES_PER_LINE)


class LabelSheetSerializer(serializers.Serializer):
    items = LabelItemSerializer(many=True, allow_empty=False, max_length=MAX_LINES)
    format = serializers.ChoiceField(choices=["xlsx", "csv"], required=False, default="xlsx")


class LabelSheetView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = LabelSheetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rows = label_rows(s.validated_data["items"])
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")

        fmt = s.validated_data["format"]
        if fmt == "xlsx":
            try:
                body = _xlsx(rows)
            except ImportError:  # openpyxl missing from an old image
                fmt = "csv"
        if fmt == "csv":
            body = _csv(rows)
            content_type = "text/csv; charset=utf-8"
        else:
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="labels-{stamp}.{fmt}"'
        response["X-Label-Count"] = str(len(rows))
        response["Access-Control-Expose-Headers"] = "Content-Disposition, X-Label-Count"
        return response
