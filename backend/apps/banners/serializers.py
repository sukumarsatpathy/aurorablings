from rest_framework import serializers
from core.media import build_media_url, validate_image_file
from .models import PromoBanner

class PromoBannerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    title_x = serializers.IntegerField(min_value=0, max_value=100, required=False)
    title_y = serializers.IntegerField(min_value=0, max_value=100, required=False)
    subtitle_x = serializers.IntegerField(min_value=0, max_value=100, required=False)
    subtitle_y = serializers.IntegerField(min_value=0, max_value=100, required=False)
    cta_x = serializers.IntegerField(min_value=0, max_value=100, required=False)
    cta_y = serializers.IntegerField(min_value=0, max_value=100, required=False)
    badge_bold_x = serializers.IntegerField(min_value=0, max_value=100, required=False)
    badge_bold_y = serializers.IntegerField(min_value=0, max_value=100, required=False)
    badge_text_x = serializers.IntegerField(min_value=0, max_value=100, required=False)
    badge_text_y = serializers.IntegerField(min_value=0, max_value=100, required=False)

    class Meta:
        model = PromoBanner
        fields = [
            'id', 'position', 'title', 'subtitle', 'badge_text', 'badge_bold',
            'cta_label', 'cta_url', 'image', 'bg_color', 'shape_color',
            'title_color', 'subtitle_color', 'badge_color', 'cta_text_color', 'cta_border_color',
            'title_x', 'title_y', 'subtitle_x', 'subtitle_y', 'cta_x', 'cta_y',
            'badge_bold_x', 'badge_bold_y', 'badge_text_x', 'badge_text_y',
            'order',
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
