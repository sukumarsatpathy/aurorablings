import sys
import os
import django
import json
from decimal import Decimal

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.catalog.models import Product
from apps.catalog.serializers import ProductListSerializer

def debug():
    p = Product.objects.first()
    if not p:
        print("No products found.")
        return
    
    # Mock request context for serializer (needed for absolute URIs)
    serializer = ProductListSerializer(p, context={'request': None})
    data = serializer.data
    print(f"Product: {p.name}")
    print(f"Variant Count: {data.get('variant_count')}")
    print(f"Total Stock: {data.get('total_stock')}")
    print(json.dumps(data, indent=2, default=str))

if __name__ == "__main__":
    debug()
