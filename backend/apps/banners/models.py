from django.db import models
from core.models import BaseModel
from core.image_optimization import (
    avif_encoder_available,
    compress_image,
    generate_avif_variants,
    generate_responsive_variants,
)

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
    image_small   = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    image_medium  = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    image_large   = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    # AVIF siblings of the three WebP derivatives above. Optional by design:
    # when the Pillow build cannot encode AVIF these stay empty and the
    # storefront's <picture> simply omits the AVIF <source>.
    image_avif_small  = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    image_avif_medium = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
    image_avif_large  = models.ImageField(upload_to='promo_banners/', blank=True, null=True)
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

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        # Only treat missing AVIF as a reason to regenerate when this Pillow
        # build can actually produce it. Without that guard, an environment
        # without the AVIF encoder would find the fields permanently empty and
        # re-run the whole pipeline on *every* save — re-encoding the master and
        # churning files through the pre_save cleanup signal each time.
        avif_missing = avif_encoder_available() and not (
            self.image_avif_small and self.image_avif_medium and self.image_avif_large
        )

        should_generate = bool(self.image) and (
            not self.pk
            or not self.image_small
            or not self.image_medium
            or not self.image_large
            or avif_missing
            or (update_fields is not None and "image" in update_fields)
        )

        if should_generate:
            src_name = getattr(self.image, "name", "") or ""
            stem = src_name.rsplit("/", 1)[-1].rsplit(".", 1)[0] if src_name else ""
            main_name, main_content = compress_image(
                self.image,
                output_dir="promo_banners",
                max_width=1800,
                quality=74,
                file_stem=stem or None,
            )
            self.image.save(main_name, main_content, save=False)
            base_stem = main_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            variants = generate_responsive_variants(
                self.image,
                output_dir="promo_banners",
                base_stem=base_stem,
                widths=(480, 768, 1200),
                quality=72,
            )
            small_name, small_content = variants["small"]
            medium_name, medium_content = variants["medium"]
            large_name, large_content = variants["large"]
            self.image_small.save(small_name, small_content, save=False)
            self.image_medium.save(medium_name, medium_content, save=False)
            self.image_large.save(large_name, large_content, save=False)

            # Additive. Empty dict when the encoder is unavailable, in which
            # case these fields stay blank and the storefront serves WebP only.
            avif = generate_avif_variants(
                self.image,
                output_dir="promo_banners",
                base_stem=base_stem,
                widths=(480, 768, 1200),
            )
            if avif:
                for label, field in (
                    ("small", self.image_avif_small),
                    ("medium", self.image_avif_medium),
                    ("large", self.image_avif_large),
                ):
                    name, content = avif[label]
                    field.save(name, content, save=False)

        super().save(*args, **kwargs)
