import sys
import os
import django
from django.utils import timezone
from datetime import timedelta
import random

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.catalog.models import Category, Product, ProductVariant, ProductMedia

def seed():
    # 1. Categories
    jewelry, _ = Category.objects.get_or_create(name="Jewelry", slug="jewelry")
    necklaces, _ = Category.objects.get_or_create(name="Necklaces", slug="necklaces", parent=jewelry)
    earrings, _ = Category.objects.get_or_create(name="Earrings", slug="earrings", parent=jewelry)
    rings, _ = Category.objects.get_or_create(name="Rings", slug="rings", parent=jewelry)

    # 2. Products
    products_data = [
        {
            "name": "Eternal Glow Diamond Necklace",
            "slug": "eternal-glow-diamond-necklace",
            "category": necklaces,
            "short_description": "Handcrafted diamond necklace.",
            "price": 599.99,
            "offer_price": 449.99,
            "rating": 4.8
        },
        {
            "name": "Midnight Bloom Earrings",
            "slug": "midnight-bloom-earrings",
            "category": earrings,
            "short_description": "Elegant floral design earrings.",
            "price": 120.00,
            "offer_price": 89.99,
            "rating": 4.5
        },
        {
            "name": "Celestial Aura Sapphire Ring",
            "slug": "celestial-aura-sapphire-ring",
            "category": rings,
            "short_description": "Deep blue sapphire ring.",
            "price": 850.00,
            "offer_price": 699.00,
            "rating": 4.9
        },
        {
            "name": "Stardust Gold Bracelet",
            "slug": "stardust-gold-bracelet",
            "category": jewelry,
            "short_description": "Minimalist 18k gold bracelet.",
            "price": 250.00,
            "offer_price": 199.00,
            "rating": 4.2
        }
    ]

    for data in products_data:
        p, created = Product.objects.get_or_create(
            slug=data["slug"],
            defaults={
                "name": data["name"],
                "category": data["category"],
                "short_description": data["short_description"],
                "rating": data["rating"],
                "is_active": True,
                "is_featured": random.choice([True, False])
            }
        )
        
        # Create Variant
        v, _ = ProductVariant.objects.get_or_create(
            product=p,
            sku=f"SKU-{p.slug.upper()}",
            defaults={
                "name": "Default",
                "price": data["price"],
                "offer_price": data["offer_price"],
                "offer_is_active": True,
                "offer_starts_at": timezone.now() - timedelta(days=1),
                "offer_ends_at": timezone.now() + timedelta(days=25),
                "stock_quantity": random.randint(5, 50),
                "is_default": True
            }
        )
        
        # Add a placeholder image if possible (using Unsplash URLs)
        image_url = "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&q=80&w=800"
        # Since ProductMedia expects a file, we won't mock files here as it's complex,
        # but the frontend will show the primary_image URL if it's stored.
        # For this demo, we'll assume the user will upload images.

    print(f"Successfully seeded {len(products_data)} products with deals.")

if __name__ == "__main__":
    seed()
