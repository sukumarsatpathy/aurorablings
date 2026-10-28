"""
catalog.label_papers
~~~~~~~~~~~~~~~~~~~~

The two label rolls the shop prints barcode labels on. Each category says which
one its products use; the label download is split by paper, because only one
roll is in the printer at a time.

Both papers carry the same data (Barcode, Name, SKU, MRP) — what differs is the
template in the label printer app, which places those columns on the roll.

    Packed sticker  40 × 15 mm, transparent, waterproof. Stuck on the white
                    side of a pouch or box (packed display).
    Tail tag        100 × 15 mm with a 64 mm printable head that folds in two
                    (32 × 15 mm per face) and a 36 mm tail that loops through
                    the piece. Loose display: rings, bangles, hanging pieces.

The list is fixed in code rather than editable in the admin: a new roll also
needs a new template in the printer app and a scan test, so adding one is a
deliberate change, not a settings tweak.
"""

from django.db import models


class LabelPaper(models.TextChoices):
    PACKED_STICKER = "packed_sticker", "Packed sticker (40 × 15 mm)"
    TAIL_TAG = "tail_tag", "Tail tag (100 × 15 mm)"


DEFAULT_LABEL_PAPER = LabelPaper.PACKED_STICKER

LABEL_PAPERS = {
    LabelPaper.PACKED_STICKER: {
        "key": LabelPaper.PACKED_STICKER.value,
        "name": "Packed sticker",
        "width_mm": 40,
        "height_mm": 15,
        "material": "Transparent, waterproof",
        "use": "Packed display — stick on the white side of the pouch or box",
        "file_slug": "packed-sticker",
    },
    LabelPaper.TAIL_TAG: {
        "key": LabelPaper.TAIL_TAG.value,
        "name": "Tail tag",
        "width_mm": 100,
        "height_mm": 15,
        "material": "White, waterproof, non-tearable",
        "use": "Loose display — 64 mm head folds into two 32 × 15 mm faces; tail loops through the piece",
        "file_slug": "tail-tag",
    },
}


def paper_info(key: str) -> dict:
    return LABEL_PAPERS.get(key) or LABEL_PAPERS[DEFAULT_LABEL_PAPER]
