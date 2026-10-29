"""
Label sheet — the file the label printer app prints barcode stickers from.

    POST /api/v1/inventory/labels/
         {items: [{variant_id, copies}], format?: "xls" | "csv" | "xlsx", paper?}

Returns a spreadsheet with ONE ROW PER STICKER (a line with copies=3 becomes
three identical rows), because label apps such as WE PRINT print one label per
row and have no notion of a "copies" column. Columns:

    Barcode | Name | SKU | MRP

Each product prints on its category's label paper (catalog.label_papers). One
file is for one roll, so a request whose items need different papers is
refused — the page asks once per paper. Pass `paper` to say which roll the file
is for; it must match every item.

Barcode is the variant's label number, sent as text so Excel doesn't turn it
into 1.00E+07. Name is the short label name (≤ 20 chars). MRP is the variant's
regular price — not a live offer price, because a sticker outlives an offer.
Whatever is printed, the till still charges the price in the database.

Printing labels never changes stock. Stock is added by receiving it (single or
bulk receive); this endpoint only reads.

Format: .xls (Excel 97–2003) is the default. The WePrint app (Detonger) that
SEZNIK printers use lists XLS, XLSX and CSV, but opened our .xlsx as "no data
found"; the old binary format is what phone label apps read most reliably.
Every cell is plain text on a sheet named "Sheet1" with the headers in row 1.
CSV is plain UTF-8 without a byte-order mark, which some apps read into the
first column name. .xlsx stays available for spreadsheets.

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
from apps.catalog.label_papers import DEFAULT_LABEL_PAPER, LabelPaper, paper_info
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


def label_rows(items, paper: str | None = None) -> tuple[list[list[str]], str]:
    """
    `items` = [{"variant_id", "copies"}] → (one row per sticker in the order
    given, the paper they print on). Lines for the same variant are added
    together. All items must share one paper, and match `paper` if given.
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
        for v in ProductVariant.objects.select_related("product__category")
        .prefetch_related("attribute_values__attribute")
        .filter(pk__in=list(merged), product__deleted_at__isnull=True)
    }
    missing = [vid for vid in merged if vid not in variants]
    if missing:
        raise ValidationError(
            f"{len(missing)} item{'s' if len(missing) != 1 else ''} no longer exist. Reload the page and try again."
        )

    papers = {
        (v.product.category.label_paper if v.product.category_id else DEFAULT_LABEL_PAPER)
        for v in variants.values()
    }
    if paper and papers != {paper}:
        wrong = sorted(paper_info(p)["name"] for p in papers - {paper})
        raise ValidationError(
            f"Some items print on a different paper ({', '.join(wrong)}). Download each paper separately."
        )
    if len(papers) > 1:
        raise ValidationError("These items use different label papers. Download each paper separately.")
    used = papers.pop()

    rows: list[list[str]] = []
    for vid, copies in merged.items():
        v = variants[vid]
        if not v.barcode:  # only possible for rows created by bulk_create
            v.save(update_fields=["barcode"])
        row = [v.barcode, v.label_text, v.sku, _mrp(v.price)]
        rows.extend([row] * copies)
    return rows, used


def _csv(rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _xls(rows) -> bytes:
    import xlwt

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Sheet1")
    text = xlwt.easyxf(num_format_str="@")
    for col, header in enumerate(HEADERS):
        ws.write(0, col, header, text)
    # Written as strings so the barcode stays "10000123", never 1.00E+07.
    for r, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            ws.write(r, col, str(value), text)
    for col, width in enumerate((12, 24, 18, 8)):
        ws.col(col).width = 256 * width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _xlsx(rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
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
    format = serializers.ChoiceField(choices=["xls", "xlsx", "csv"], required=False, default="xls")
    paper = serializers.ChoiceField(choices=LabelPaper.choices, required=False)


class LabelSheetView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = LabelSheetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rows, paper = label_rows(s.validated_data["items"], s.validated_data.get("paper"))
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")

        fmt = s.validated_data["format"]
        builders = {
            "xls": (_xls, "application/vnd.ms-excel"),
            "xlsx": (_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }
        body = None
        if fmt in builders:
            build, content_type = builders[fmt]
            try:
                body = build(rows)
            except ImportError:  # library missing from an old image
                fmt = "csv"
        if fmt == "csv":
            body = _csv(rows)
            content_type = "text/csv; charset=utf-8"

        response = HttpResponse(body, content_type=content_type)
        slug = paper_info(paper)["file_slug"]
        response["Content-Disposition"] = f'attachment; filename="labels-{slug}-{stamp}.{fmt}"'
        response["X-Label-Count"] = str(len(rows))
        response["X-Label-Paper"] = paper
        response["Access-Control-Expose-Headers"] = "Content-Disposition, X-Label-Count, X-Label-Paper"
        return response
