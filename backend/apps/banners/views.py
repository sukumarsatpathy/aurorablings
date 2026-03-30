from django.core.cache import cache
from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.exceptions import ValidationError as DRFValidationError
from core.media import delete_file_if_exists
from .models import PromoBanner
from .serializers import PromoBannerSerializer
from .constants import PROMO_BANNERS_ACTIVE_CACHE_KEY

class PromoBannerViewSet(viewsets.ModelViewSet):
    queryset = PromoBanner.objects.all()
    serializer_class = PromoBannerSerializer
    
    def get_permissions(self):
        if self.action in ['active', 'list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """
        Returns active banners ordered by 'order', cached in Redis for 5 minutes.
        """
        cached_data = cache.get(PROMO_BANNERS_ACTIVE_CACHE_KEY)
        if cached_data:
            return Response(cached_data)

        active_banners = PromoBanner.objects.filter(is_active=True).order_by('order')
        serializer = self.get_serializer(active_banners, many=True)
        data = serializer.data
        
        # Cache the result for 5 minutes (300 seconds)
        cache.set(PROMO_BANNERS_ACTIVE_CACHE_KEY, data, timeout=300)
        
        return Response(data)

    def perform_destroy(self, instance):
        """Soft delete: set is_active=False"""
        delete_file_if_exists(instance.image)
        instance.image = None
        instance.is_active = False
        instance.save(update_fields=["image", "is_active", "updated_at"])

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise DRFValidationError({"position": ["This banner position is already used."]})

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise DRFValidationError({"position": ["This banner position is already used."]})

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """Bulk updates the order of banners"""
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of {id, order} objects"}, status=status.HTTP_400_BAD_REQUEST)
        
        for item in data:
            banner_id = item.get('id')
            order = item.get('order')
            if banner_id is not None and order is not None:
                PromoBanner.objects.filter(id=banner_id).update(order=order)
        
        return Response({"status": "reordered"}, status=status.HTTP_200_OK)
