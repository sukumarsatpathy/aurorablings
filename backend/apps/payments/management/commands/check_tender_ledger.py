"""
Audit the tender ledger against the orders it settles.

Run this after the backfill migration, after any bulk data change, and whenever a
day's takings don't tie out.  It answers one question: does every order's ledger
agree with the order itself?

    python manage.py check_tender_ledger
    python manage.py check_tender_ledger --since 2026-08-01 --limit 50
    python manage.py check_tender_ledger --fix-status

Exits non-zero if any problem is found, so it can be wired into a cron or a
deploy check later.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum
from django.utils.dateparse import parse_date

from apps.orders.models import Order, PaymentStatus
from apps.payments.models import TenderStatus
from apps.payments import tender_service as ledger

ZERO = Decimal("0.00")


class Command(BaseCommand):
    help = "Verify that every order's tender ledger agrees with the order."

    def add_arguments(self, parser):
        parser.add_argument("--since", help="Only orders created on or after this date (YYYY-MM-DD).")
        parser.add_argument("--limit", type=int, default=0, help="Stop after N problems.")
        parser.add_argument(
            "--fix-status",
            action="store_true",
            help="Correct payment_status where it disagrees with the ledger. "
                 "Only touches the status field; never invents or deletes tenders.",
        )

    def handle(self, *args, **opts):
        orders = Order.objects.all().order_by("created_at")

        if opts["since"]:
            since = parse_date(opts["since"])
            if not since:
                self.stderr.write(self.style.ERROR("--since must be YYYY-MM-DD"))
                return
            orders = orders.filter(created_at__date__gte=since)

        orders = orders.annotate(
            settled=Sum(
                "tenders__amount_applied",
                filter=Q(tenders__status=TenderStatus.CAPTURED),
            )
        )

        checked = 0
        problems: list[str] = []
        fixed = 0

        for order in orders.iterator(chunk_size=500):
            checked += 1
            settled = order.settled or ZERO
            total = order.grand_total or ZERO

            # 1. Over-collection. Should be impossible via tender_service, so if it
            #    appears the money came in some other way and needs a human.
            if settled > total:
                problems.append(
                    f"{order.order_number}: tenders total {settled} exceeds order total {total}"
                )

            # 2. A paid order with nothing behind it, or an unpaid one holding money.
            expected = ledger.derive_payment_status(order)
            if expected != order.payment_status:
                problems.append(
                    f"{order.order_number}: payment_status is {order.payment_status!r} "
                    f"but the ledger says {expected!r} (settled {settled} of {total})"
                )
                if opts["fix_status"]:
                    order.payment_status = expected
                    order.save(update_fields=["payment_status"])
                    fixed += 1

            # 3. Cash arithmetic. received - change must equal applied, or the day's
            #    takings are wrong even though the order looks fine.
            for tender in order.tenders.filter(status=TenderStatus.CAPTURED, method="cash"):
                received = tender.cash_received or ZERO
                change = tender.change_given or ZERO
                if received - change != tender.amount_applied:
                    problems.append(
                        f"{order.order_number}: cash tender {tender.id} does not balance — "
                        f"received {received} - change {change} != applied {tender.amount_applied}"
                    )

            # 4. Paid orders with an empty ledger. Expected for pre-backfill data only.
            if order.payment_status == PaymentStatus.PAID and settled == ZERO and total > ZERO:
                problems.append(
                    f"{order.order_number}: marked paid but has no tenders "
                    f"(backfill may not have run)"
                )

            if opts["limit"] and len(problems) >= opts["limit"]:
                problems.append(f"… stopped at --limit {opts['limit']}")
                break

        self.stdout.write(f"Checked {checked} order(s).")

        if opts["fix_status"] and fixed:
            self.stdout.write(self.style.WARNING(f"Corrected payment_status on {fixed} order(s)."))

        if not problems:
            self.stdout.write(self.style.SUCCESS("Ledger agrees with every order."))
            return

        self.stdout.write(self.style.ERROR(f"\n{len(problems)} problem(s):"))
        for line in problems:
            self.stdout.write(f"  - {line}")

        raise SystemExit(1)
