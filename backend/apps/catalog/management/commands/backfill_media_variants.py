from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.catalog.models import ProductMedia


class Command(BaseCommand):
    """Populate image_small / image_medium / image_large for legacy media rows.

    ProductMedia.save() generates these derivatives on upload, but rows created
    before migration 0010_productmedia_image_variants have them null. Product
    listings fall back to the full-size master for those rows, which is exactly
    the payload cost the derivatives exist to avoid.

    Re-saving each row triggers the generation logic in ProductMedia.save().
    Safe to re-run: rows that already have all three derivatives are skipped.

    DESTRUCTIVE — READ BEFORE RUNNING WITH --apply
    ----------------------------------------------
    ProductMedia.save() does not only add the missing derivatives. It also
    re-encodes the master image via compress_image() (max 1800px, WebP, q74)
    and assigns it to self.image under a new .webp name. The pre_save signal
    cleanup_replaced_product_media() then deletes the previous file, because
    its name changed.

    So for every row processed:
      - the original .jpg/.png master is DELETED from disk
      - it is replaced by a re-encoded .webp
      - three new derivative files are written

    Re-encoding an already-lossy JPEG to WebP is lossy again. It is a
    reasonable trade for web delivery, but it cannot be undone from the
    application. Back up MEDIA_ROOT before the first --apply run, and use
    --limit for a small trial pass to eyeball the output quality first.

    Usage:
        python manage.py backfill_media_variants                    # dry run
        python manage.py backfill_media_variants --apply --limit 5  # trial
        python manage.py backfill_media_variants --apply
        python manage.py backfill_media_variants --apply --batch-size 50
    """

    help = "Generate missing responsive image derivatives for ProductMedia rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually re-save rows. Without this, only reports what would change.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Rows to process per iteration. Lower this if the box is memory-tight.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N rows (0 = no limit). Useful for a cautious first pass.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        batch_size = max(1, int(options["batch_size"]))
        limit = max(0, int(options["limit"]))

        # The derivative fields are blank=True, null=True, so an "unset" row can
        # hold either NULL or "". Both cases must be matched explicitly —
        # `__in=["", None]` compiles to SQL `IN ('', NULL)`, and `= NULL` is
        # never true, so the None arm would silently match nothing.
        def unset(field: str) -> Q:
            return Q(**{f"{field}__isnull": True}) | Q(**{field: ""})

        missing = (
            ProductMedia.objects
            .filter(unset("image_small") | unset("image_medium") | unset("image_large"))
            .exclude(image__isnull=True)
            .exclude(image="")
        )

        total = missing.count()
        if not total:
            self.stdout.write(self.style.SUCCESS("All media rows already have derivatives."))
            return

        target = min(total, limit) if limit else total
        self.stdout.write(
            f"{total} media row(s) missing derivatives; processing {target}."
        )

        if not apply_changes:
            for media in missing.only("id", "image")[:10]:
                self.stdout.write(f"  would regenerate: {media.image.name}")
            if target > 10:
                self.stdout.write(f"  ... and {target - 10} more")
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — re-run with --apply to write changes.\n"
                    "NOTE: --apply also re-encodes each master image to WebP and\n"
                    "deletes the original file (see the class docstring).\n"
                    "Back up MEDIA_ROOT first, and consider --apply --limit 5 as a trial."
                )
            )
            return

        processed = 0
        failed = 0
        pks = list(missing.values_list("pk", flat=True)[:target])

        for start in range(0, len(pks), batch_size):
            chunk = pks[start:start + batch_size]
            for media in ProductMedia.objects.filter(pk__in=chunk):
                try:
                    # save() regenerates whatever is missing; no field list so
                    # the should_generate branch in the model sees a full save.
                    media.save()
                    processed += 1
                except Exception as exc:  # noqa: BLE001 - report and continue
                    failed += 1
                    self.stderr.write(
                        self.style.ERROR(f"  failed {media.pk} ({media.image.name}): {exc}")
                    )
            self.stdout.write(f"  {min(start + batch_size, len(pks))}/{len(pks)} done")

        self.stdout.write(
            self.style.SUCCESS(f"Regenerated {processed} row(s).")
            if not failed
            else self.style.WARNING(f"Regenerated {processed} row(s), {failed} failed.")
        )
