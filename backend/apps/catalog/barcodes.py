"""
catalog.barcodes
~~~~~~~~~~~~~~~~

Barcode numbers and the short name printed on a counter label.

The barcode on a label identifies a variant and nothing else. Price is printed
as text beside it but never encoded in the bars: prices change, offers come and
go, and a price inside a printed barcode is a label that is wrong the day the
price moves — or a label anyone can reprint cheaper. The till scans the number
and reads today's price from the database.

Numbers are 8 digits, starting at 10000001:

* digits only, because Code 128 packs digit pairs into one symbol, so the
  barcode is ~25% narrower than an alphanumeric code of the same length. On a
  40 mm label printed at 203 dpi that is the difference between bars a budget
  scanner reads and bars it doesn't;
* fixed length, so a character dropped over Bluetooth produces a 7-digit read
  that cannot match anything, rather than a different valid product;
* never reused and never changed — a printed label must keep pointing at the
  same piece for as long as it exists.

Allocation uses a Postgres sequence, so two variants created at the same moment
can't be handed the same number. Other databases (the SQLite fallback used by
some local test runs) take max + 1, which is fine for a single writer.
"""

from __future__ import annotations

import re

from django.db import connection

SEQUENCE_NAME = "catalog_variant_barcode_seq"
FIRST_BARCODE = 10_000_001
BARCODE_LENGTH = 8
BARCODE_RE = re.compile(r"^\d{8}$")

# Room on a 40 × 15 mm label at the smallest readable size.
LABEL_NAME_MAX = 20


def is_barcode(value: str) -> bool:
    return bool(BARCODE_RE.match((value or "").strip()))


def next_variant_barcode() -> str:
    """Allocate the next unused barcode number."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(%s)", [SEQUENCE_NAME])
            return str(cursor.fetchone()[0])

    from .models import ProductVariant  # local: models imports this module

    highest = (
        ProductVariant.objects.filter(barcode__regex=r"^\d{8}$")
        .order_by("-barcode")
        .values_list("barcode", flat=True)
        .first()
    )
    return str(max(int(highest) + 1, FIRST_BARCODE) if highest else FIRST_BARCODE)


# ─────────────────────────────────────────────────────────────
#  Label name
# ─────────────────────────────────────────────────────────────

# Option values shortened the same way on every label, so staff learn them once.
_ABBREVIATIONS = {
    "black": "Blk",
    "blue": "Blu",
    "brown": "Brn",
    "golden": "Gld",
    "gold": "Gld",
    "green": "Grn",
    "grey": "Gry",
    "gray": "Gry",
    "maroon": "Mrn",
    "multicolor": "Multi",
    "multicolour": "Multi",
    "multi color": "Multi",
    "multi colour": "Multi",
    "orange": "Org",
    "pink": "Pnk",
    "purple": "Ppl",
    "rose gold": "RGld",
    "silver": "Slv",
    "white": "Wht",
    "yellow": "Ylw",
    "small": "S",
    "medium": "M",
    "large": "L",
    "extra large": "XL",
    "adjustable": "Adj",
    "free size": "Free",
}


def _short_option(value: str) -> str:
    text = " ".join((value or "").split())
    return _ABBREVIATIONS.get(text.lower(), text)


def _fit_words(text: str, room: int) -> str:
    """Cut at a word boundary to fit `room`; hard-cut only if one word is too long."""
    text = " ".join((text or "").split())
    if len(text) <= room:
        return text
    out = ""
    for word in text.split(" "):
        candidate = f"{out} {word}".strip()
        if len(candidate) > room:
            break
        out = candidate
    return out or text[:room]


def default_label_name(variant) -> str:
    """
    Product name + variant options, shortened to fit a 40 mm label.

    "Kundan Choker Necklace" / Green → "Kundan Choker Grn". The option part is
    kept whole where possible — it is what tells two neighbouring pieces apart —
    and the product name gives way, cut at a word boundary.
    """
    product_name = variant.product.name if variant.product_id else ""
    values = []
    if variant.pk:
        # .all() + a Python sort, so a caller that prefetched
        # "attribute_values__attribute" pays no query per label.
        ordered = sorted(
            variant.attribute_values.all(),
            key=lambda av: (av.attribute.sort_order, av.attribute.name),
        )
        values = [_short_option(av.value) for av in ordered]
    options = " ".join(v for v in values if v)
    if not options:
        return _fit_words(product_name or variant.name or variant.sku, LABEL_NAME_MAX)

    options = _fit_words(options, LABEL_NAME_MAX)
    room = LABEL_NAME_MAX - len(options) - 1
    if room < 3:
        return options
    name = _fit_words(product_name, room)
    return f"{name} {options}".strip()
