"""
Fill swatch colours for attributes that already exist, so no colour dot
disappears when the site switches to hex codes set on the Attributes page:

- attributes named like "Color"/"Colour" get show_swatches = True;
- their options get a hex code from the colour-name list the site used
  until now (exact name first, then the last colour word: "Dusky Rose Pink"
  → pink);
- each product's copy of an attribute/option gets the same values.

Options with no recognisable colour name stay blank; set them by hand.
"""

import re

from django.db import migrations

NAMED = {
    "amber": "#FFBF00",
    "amber orange": "#F39C12",
    "antique gold": "#A8892C",
    "aqua": "#5FD3D3",
    "baby pink": "#F4C2C2",
    "beige": "#E3D3B4",
    "black": "#111111",
    "blue": "#1E5BB8",
    "blush": "#F4C2C2",
    "blush pink": "#F4C2C2",
    "bottle green": "#006A4E",
    "bronze": "#A97142",
    "brown": "#7A4A26",
    "burgundy": "#800020",
    "champagne": "#E8D4A8",
    "charcoal": "#36454F",
    "coffee": "#6F4E37",
    "coffee brown": "#6F4E37",
    "copper": "#B87333",
    "coral": "#FF7F50",
    "cream": "#F3E9D2",
    "cyan": "#00B7C7",
    "dark blue": "#1B2F6B",
    "dark green": "#1E5631",
    "dark pink": "#D1477A",
    "dusty pink": "#D4A5A5",
    "emerald": "#1F8A5B",
    "emerald green": "#1F8A5B",
    "fuchsia": "#D6249F",
    "gold": "#C9A227",
    "golden": "#C9A227",
    "gray": "#8A8A8A",
    "green": "#2E7D32",
    "grey": "#8A8A8A",
    "hot pink": "#FF4F9A",
    "ice blue": "#C9E6F2",
    "ivory": "#F4EFE1",
    "lavender": "#B9A7E0",
    "lemon": "#F6E05E",
    "lemon yellow": "#F6E05E",
    "light blue": "#9CC8EC",
    "light green": "#90D890",
    "light pink": "#F7C6D0",
    "lilac": "#C8A2C8",
    "lime green": "#9ACD32",
    "magenta": "#C2185B",
    "malachite": "#0B6E4F",
    "malachite green": "#0B6E4F",
    "maroon": "#7B1E2B",
    "mauve": "#C49BBB",
    "mint": "#98D8B5",
    "mint green": "#98D8B5",
    "mustard": "#D4A017",
    "mustard yellow": "#D4A017",
    "navy blue": "#1F2F5C",
    "nude": "#E3BC9A",
    "off white": "#F5F1E6",
    "olive": "#708238",
    "olive green": "#708238",
    "onion pink": "#E8A0A8",
    "orange": "#EF7D1A",
    "oxidised": "#5B5B5B",
    "oxidized": "#5B5B5B",
    "parrot green": "#3FB83F",
    "pastel pink": "#F8C8DC",
    "peach": "#F6B48F",
    "peacock": "#00727A",
    "peacock blue": "#00727A",
    "pearl": "#EFE8DA",
    "pearl white": "#F3EEE4",
    "pink": "#E86FA4",
    "powder blue": "#B0D4E8",
    "purple": "#6B2FA0",
    "rani": "#E0218A",
    "rani pink": "#E0218A",
    "red": "#C62828",
    "rose gold": "#B76E79",
    "rose pink": "#E8789A",
    "royal blue": "#2747A8",
    "ruby red": "#9B111E",
    "rust": "#B7410E",
    "rust orange": "#B7410E",
    "salmon": "#FA8072",
    "sea green": "#2E8B57",
    "silver": "#C0C0C0",
    "sky blue": "#76B5E8",
    "tan": "#D2B48C",
    "teal": "#127A7A",
    "turquoise": "#30B5B0",
    "violet": "#7F3FBF",
    "white": "#FFFFFF",
    "wine": "#722F37",
    "yellow": "#F2C94C",
}


def _guess(value: str) -> str:
    key = re.sub(r"\s+", " ", (value or "").strip().lower())
    if key in NAMED:
        return NAMED[key]
    for word in reversed([w for w in re.split(r"[\s/&,-]+", key) if w]):
        if word in NAMED:
            return NAMED[word]
    return ""


def fill(apps, schema_editor):
    GlobalAttribute = apps.get_model("catalog", "GlobalAttribute")
    GlobalAttributeOption = apps.get_model("catalog", "GlobalAttributeOption")
    Attribute = apps.get_model("catalog", "Attribute")
    AttributeValue = apps.get_model("catalog", "AttributeValue")
    colour_name = re.compile(r"colou?r", re.I)

    for ga in GlobalAttribute.objects.all():
        if not colour_name.search(ga.name):
            continue
        ga.show_swatches = True
        ga.save(update_fields=["show_swatches"])
        hex_by_value = {}
        for opt in GlobalAttributeOption.objects.filter(global_attribute=ga):
            if not opt.hex_code:
                opt.hex_code = _guess(opt.value)
                if opt.hex_code:
                    opt.save(update_fields=["hex_code"])
            if opt.hex_code:
                hex_by_value[opt.value.lower()] = opt.hex_code
        Attribute.objects.filter(name__iexact=ga.name).update(show_swatches=True)
        for val in AttributeValue.objects.filter(attribute__name__iexact=ga.name, hex_code=""):
            code = hex_by_value.get(val.value.lower()) or _guess(val.value)
            if code:
                val.hex_code = code
                val.save(update_fields=["hex_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0015_attribute_swatch_colours"),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
