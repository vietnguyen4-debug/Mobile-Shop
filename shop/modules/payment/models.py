from mongoengine import *

from ...core.mixins import AuditMixin


class Payment(Document, AuditMixin):
    checkout = ReferenceField("Checkout", required=True)
    user = ReferenceField("User", required=False, null=True)
    session_id = StringField(required=False, max_length=120)
    method = StringField(required=True, default="online", choices=("online",))
    provider = StringField(required=False, max_length=50)
    provider_ref = StringField(required=False, max_length=120)
    amount = FloatField(required=True, min_value=0)
    currency = StringField(default="VND", max_length=10)
    status = StringField(
        default="pending",
        choices=("pending", "completed", "cancelled"),
    )
    # Provider result metadata (optional)
    provider_rsp_code = StringField(required=False, max_length=10)
    provider_txn_no = StringField(required=False, max_length=50)
    provider_bank_code = StringField(required=False, max_length=20)
    provider_bank_tran_no = StringField(required=False, max_length=50)
    provider_card_type = StringField(required=False, max_length=20)
    # VNPAY uses YYYYMMDDHHMMSS for CreateDate/TransactionDate.
    provider_create_date = StringField(required=False, max_length=20)
    provider_pay_date = StringField(required=False, max_length=20)
    note = StringField()
    paid_at = DateTimeField()

    meta = {
        "collection": "payment",
        # Match existing indexes in DB (background: false) to avoid option mismatch
        "index_background": False,
        "indexes": [
            {
                "fields": ["checkout", "method"],
                # Allow multiple payments per checkout/method (non-unique)
                "name": "idx_payment_checkout_method",
            },
            {"fields": ["status", "-created_at"], "name": "idx_payment_status_created"},
        ],
    }
