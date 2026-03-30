from rest_framework import serializers
from core.media import build_media_url, validate_image_file
from .models import PromoBanner

class PromoBannerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = PromoBanner
        fields = [
            'id', 'position', 'title', 'subtitle', 'badge_text', 'badge_bold',
            'cta_label', 'cta_url', 'image', 'bg_color', 'shape_color', 'order',
            'is_active', 'created_at', 'updated_at'
        ]

    def validate_image(self, value):
        if value in (None, ""):
            return value
        try:
            return validate_image_file(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.image:
            ret['image'] = build_media_url(instance.image, request=self.context.get('request'))
        return ret
