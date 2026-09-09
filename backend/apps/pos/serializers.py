import re

from rest_framework import serializers

from apps.pos.models import POSCashMovement, POSShift, POSTerminal


class POSTerminalSerializer(serializers.ModelSerializer):
    """
    Read shape. The counter only needs the first five fields; the settings screen
    needs to know whether a terminal is in use before anyone deactivates or
    deletes it, so those counts are derived here rather than guessed in the UI.
    """

    has_open_shift = serializers.SerializerMethodField()
    shift_count = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()

    class Meta:
        model = POSTerminal
        fields = [
            "id", "code", "name", "location", "is_active", "created_at",
            "has_open_shift", "shift_count", "order_count",
        ]
        read_only_fields = ["id", "created_at"]

    def get_has_open_shift(self, terminal) -> bool:
        return terminal.shifts.filter(status="open").exists()

    def get_shift_count(self, terminal) -> int:
        return terminal.shifts.count()

    def get_order_count(self, terminal) -> int:
        return terminal.orders.count()


class POSTerminalWriteSerializer(serializers.ModelSerializer):
    """
    Write shape. ``code`` is printed on receipts and used by staff to tell one
    till from another, so it is normalised to upper case here — otherwise
    "stall-01" and "STALL-01" are two terminals and the uniqueness constraint
    never notices.
    """

    class Meta:
        model = POSTerminal
        fields = ["code", "name", "location", "is_active"]

    def validate_code(self, value):
        code = (value or "").strip().upper()
        if not code:
            raise serializers.ValidationError("A code is required.")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", code):
            raise serializers.ValidationError(
                "Use letters, digits, dot, dash or underscore only, e.g. STALL-01."
            )
        clash = POSTerminal.objects.filter(code=code)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A terminal with this code already exists.")
        return code

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("A name is required.")
        return name


class POSCashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSCashMovement
        fields = ["id", "movement_type", "amount", "reason", "order", "created_at"]


class POSShiftSerializer(serializers.ModelSerializer):
    terminal_code = serializers.CharField(source="terminal.code", read_only=True)
    opened_by_name = serializers.CharField(source="opened_by.email", read_only=True)
    cash_movements = POSCashMovementSerializer(many=True, read_only=True)

    # Live figures, derived rather than stored, so the counter always sees the
    # ledger's answer rather than a cached one.
    cash_taken = serializers.SerializerMethodField()
    expected_cash_now = serializers.SerializerMethodField()
    part_paid_orders = serializers.SerializerMethodField()

    class Meta:
        model = POSShift
        fields = [
            "id", "terminal", "terminal_code", "status",
            "opened_by", "opened_by_name", "opened_at", "opening_float",
            "closed_by", "closed_at", "counted_cash", "expected_cash", "variance",
            "close_note", "cash_taken", "expected_cash_now", "part_paid_orders",
            "cash_movements",
        ]

    def get_cash_taken(self, shift):
        from apps.pos import services
        return str(services.cash_taken(shift))

    def get_expected_cash_now(self, shift):
        from apps.pos import services
        return str(services.expected_cash(shift))

    def get_part_paid_orders(self, shift):
        from apps.pos import services
        return [
            {"id": str(o.id), "order_number": o.order_number, "grand_total": str(o.grand_total)}
            for o in services.open_part_paid_orders(shift)
        ]


class OpenShiftSerializer(serializers.Serializer):
    terminal = serializers.UUIDField()
    opening_float = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)


class CloseShiftSerializer(serializers.Serializer):
    counted_cash = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    force = serializers.BooleanField(default=False)


class CashMovementCreateSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(choices=["pay_in", "pay_out", "refund"])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(max_length=255)
    order = serializers.UUIDField(required=False, allow_null=True)


class CashTenderSerializer(serializers.Serializer):
    """
    Note what is *not* here: the order total, or any price. The counter tells us
    how much cash it took; what the sale is worth is the server's business.
    """
    order = serializers.UUIDField()
    amount_applied = serializers.DecimalField(max_digits=12, decimal_places=2)
    cash_received = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class VoidSaleSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class POSLineItemSerializer(serializers.Serializer):
    """
    What the counter is allowed to say about a line: which variant, how many.
    Notably absent: price. That is the server's to decide.
    """
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class POSQuoteSerializer(serializers.Serializer):
    items = POSLineItemSerializer(many=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=50)
    # A quote has to know how the goods are leaving, because that decides whether
    # shipping is charged. Defaulted, so an existing caller keeps working.
    fulfilment_type = serializers.ChoiceField(choices=["carry_away", "ship"], default="carry_away")


class POSOrderCreateSerializer(POSQuoteSerializer):
    shift = serializers.UUIDField()
    contact_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    # Separate from the address itself: staff may take an email purely to send
    # the receipt, without the customer wanting a login.
    create_account = serializers.BooleanField(default=True)
    shipping_address = serializers.DictField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ManualDiscountSerializer(serializers.Serializer):
    percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    reason = serializers.CharField(max_length=50)
    # Present only when the discount exceeds the staff ceiling. A manager types
    # their own credentials at the counter; there is no separate PIN to leak.
    approver_email = serializers.EmailField(required=False, allow_blank=True)
    approver_password = serializers.CharField(required=False, allow_blank=True)
