from django.db import models
from core.models import BaseModel

class PromoBanner(BaseModel):
    POSITION_CHOICES = [
        ('top-left', 'Top Left'),
        ('top-right', 'Top Right'),
        ('bottom-left', 'Bottom Left'),
        ('bottom-right', 'Bottom Right'),
        ('dual-banner-left', 'Dual Banner Left (Blueberry)'),
        ('dual-banner-right', 'Dual Banner Right (Blueberry)'),
    ]
    position      = models.CharField(max_length=40, choices=POSITION_CHOICES, unique=True)
    title         = models.CharField(max_length=120, blank=True, default="")
    subtitle      = models.CharField(max_length=200, blank=True)
    badge_text    = models.CharField(max_length=60, blank=True)   # e.g. "off select silver ring"
    badge_bold    = models.CharField(max_length=40, blank=True)   # e.g. "50%"
    cta_label     = models.CharField(max_length=40, default='Shop Now')
    cta_url       = models.CharField(max_length=255)
    image         = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    bg_color      = models.CharField(max_length=20, default='#f5f0eb')  # fallback bg
    shape_color   = models.CharField(max_length=20, default='#f4dab4')
    title_color   = models.CharField(max_length=20, default='#1a1a1a')
    subtitle_color = models.CharField(max_length=20, default='#1a1a1a')
    badge_color   = models.CharField(max_length=20, default='#1a1a1a')
    cta_text_color = models.CharField(max_length=20, default='#1a1a1a')
    cta_border_color = models.CharField(max_length=20, default='#1a1a1a')
    title_x       = models.PositiveSmallIntegerField(default=8)
    title_y       = models.PositiveSmallIntegerField(default=46)
    subtitle_x    = models.PositiveSmallIntegerField(default=8)
    subtitle_y    = models.PositiveSmallIntegerField(default=64)
    cta_x         = models.PositiveSmallIntegerField(default=8)
    cta_y         = models.PositiveSmallIntegerField(default=80)
    badge_bold_x  = models.PositiveSmallIntegerField(default=8)
    badge_bold_y  = models.PositiveSmallIntegerField(default=22)
    badge_text_x  = models.PositiveSmallIntegerField(default=22)
    badge_text_y  = models.PositiveSmallIntegerField(default=22)
    order         = models.PositiveSmallIntegerField(default=0)
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Promotional Banner"
        verbose_name_plural = "Promotional Banners"

    def __str__(self):
        label = self.title or "Untitled Banner"
        return f"{self.get_position_display()} - {label}"
