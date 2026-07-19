from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.banners.models import PromoBanner


class Command(BaseCommand):
    """Populate image_small / image_medium / image_large for legacy promo banners.

    PromoBanner.save() generates these derivatives on upload, but rows created
    before migration 0004_promobanner_image_variants have them null. The
    storefront card (PromoBannerCard.jsx) builds its srcSet from those three
    fields and filters out the empty ones, so a row with no derivatives
    collapses to a single candidate pointing at the full-size master. Mobile
    then downloads a ~2400px image for a ~390px slot.

    Re-saving each row triggers the generation logic in PromoBanner.save().
    Safe to re-run: rows that already have all three derivatives are skipped.

    DESTRUCTIVE — READ BEFORE RUNNING WITH --apply
    ----------------------------------------------
    PromoBanner.save() does not only add the missing derivatives. It also
    re-encodes the master via compress_image() (max 1800px, q74) and assigns it
    to self.image under a new name. The pre_save receiver
    cleanup_replaced_banner_image() (apps/banners/signals.py) then deletes the
    previous file, because its name changed.

    So for every row processed:
      - the original master file is DELETED from disk
      - it is replaced by a re-encoded one
      - three new derivative files are written

    Re-encoding an already-lossy JPEG is lossy again. Reasonable for web
    delivery, but not undoable from the application. Back up MEDIA_ROOT before
    the first --apply run, and use --limit for a small trial pass to eyeball
    output quality first.

    Banners are far more visually prominent than product thumbnails and there
    are only a handful of them, so a trial pass is cheap. Do it.

    Usage:
        python manage.py backfill_banner_variants                    # dry run
        python manage.py backfill_banner_variants --apply --limit 1  # trial
        python manage.py backfill_banner_variants --apply
    """

    help = "Generate missing responsive image derivatives for PromoBanner rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually re-save rows. Without this, only reports what would change.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N rows (0 = no limit). Useful for a cautious first pass.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        limit = max(0, int(options["limit"]))

        # Hard stop if Pillow is unavailable. core/image_optimization.py degrades
        # silently when Image is None: it writes the raw bytes out under a .bin
        # extension instead of raising. Combined with --apply that would delete
        # every original master and replace it with an unservable .bin file.
        # Not recoverable from the application, so refuse to start.
        from core import image_optimization

        if getattr(image_optimization, "Image", None) is None:
            raise CommandError(
                "Pillow is not importable, so image_optimization would write .bin "
                "files instead of WebP and --apply would destroy the originals. "
                "Install Pillow before running this command."
            )

        # AVIF is optional, not fatal: PromoBanner.save() skips it and the
        # storefront <picture> falls through to WebP. But if the operator is
        # running this expecting AVIF output, silence would be misleading.
        if not image_optimization.avif_encoder_available():
            self.stdout.write(
                self.style.WARNING(
                    "AVIF encoder unavailable (needs Pillow >= 11.3). Banners will "
                    "get WebP derivatives only; the storefront will omit the AVIF "
                    "<source>. Re-run after upgrading Pillow to add AVIF."
                )
            )

        # The derivative fields are blank=True, null=True, so an "unset" row can
        # hold either NULL or "". Both must be matched explicitly — an
        # `__in=["", None]` compiles to SQL `IN ('', NULL)`, and `= NULL` is
        # never true, so the None arm would silently match nothing.
        def unset(field: str) -> Q:
            return Q(**{f"{field}__isnull": True}) | Q(**{field: ""})

        needs_work = unset("image_small") | unset("image_medium") | unset("image_large")

        # Only look for absent AVIF when this build can produce it. Otherwise
        # every row would match forever and each run would pointlessly re-encode
        # the masters it already processed.
        if image_optimization.avif_encoder_available():
            needs_work |= (
                unset("image_avif_small")
                | unset("image_avif_medium")
                | unset("image_avif_large")
            )

        missing = (
            PromoBanner.objects
            .filter(needs_work)
            .exclude(image__isnull=True)
            .exclude(image="")
            .order_by("order", "pk")
        )

        total = missing.count()
        if not total:
            self.stdout.write(self.style.SUCCESS("All promo banners already have derivatives."))
            return

        target = min(total, limit) if limit else total
        self.stdout.write(f"{total} banner(s) missing derivatives; processing {target}.")

        if not apply_changes:
            for banner in missing[:target]:
                self.stdout.write(f"  would regenerate: [{banner.position}] {banner.image.name}")
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — re-run with --apply to write changes.\n"
                    "NOTE: --apply also re-encodes each master image and deletes\n"
                    "the original file (see the class docstring).\n"
                    "Back up MEDIA_ROOT first, and consider --apply --limit 1 as a trial."
                )
            )
            return

        processed = 0
        failed = 0
        pks = list(missing.values_list("pk", flat=True)[:target])

        for pk in pks:
            banner = PromoBanner.objects.get(pk=pk)
            try:
                # Full save with no update_fields, so the should_generate branch
                # in the model sees a complete save and regenerates what's missing.
                banner.save()
                processed += 1
                self.stdout.write(f"  regenerated [{banner.position}] -> {banner.image.name}")
            except Exception as exc:  # noqa: BLE001 - report and continue
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"  failed {banner.pk} ({banner.position}): {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Regenerated {processed} banner(s).")
            if not failed
            else self.style.WARNING(f"Regenerated {processed} banner(s), {failed} failed.")
        )
