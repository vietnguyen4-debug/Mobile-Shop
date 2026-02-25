import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from flask import request, redirect
from flask_jwt_extended import get_jwt_identity, jwt_required

from ...core.rbac import roles_required
from ...core.responses import created, ok
from ...core.exceptions import AppError
from ...core.utils import sanitize_session_id
from . import bp, bp_admin
from .services import (
    s_create_online_payment,
    s_handle_vnpay_webhook,
    s_inspect_vnpay_return,
    s_admin_query_vnpay,
    s_get_payment,
    s_list_payments_by_checkout,
)

SESSION_COOKIE_NAME = "session_id"


def _extract_session_id() -> str | None:
    header_candidate = sanitize_session_id(request.headers.get("X-Session-Id"))
    if header_candidate:
        return header_candidate

    query_candidate = sanitize_session_id(request.args.get("session_id", type=str))
    if query_candidate:
        return query_candidate

    cookie_candidate = sanitize_session_id(request.cookies.get(SESSION_COOKIE_NAME))
    if cookie_candidate:
        return cookie_candidate

    return None


@bp.get("")
@jwt_required(optional=True)
def r_list_payments():
    checkout_id = request.args.get("checkout_id", type=str)
    if not checkout_id:
        raise AppError("checkout_id query parameter is required", 400, name="INVALID_CHECKOUT")
    session_id = _extract_session_id()
    payments = s_list_payments_by_checkout(get_jwt_identity(), session_id, checkout_id)
    return ok(payments, "Payments retrieved successfully.")


@bp.get("/<payment_id>")
@jwt_required(optional=True)
def r_get_payment(payment_id):
    session_id = _extract_session_id()
    payment = s_get_payment(payment_id, get_jwt_identity(), session_id)
    return ok(payment, "Payment retrieved successfully.")


@bp_admin.post("/<payment_id>/vnpay/query")
@jwt_required()
@roles_required("admin")
def r_query_vnpay(payment_id):
    data = request.get_json(silent=True) or {}
    result = s_admin_query_vnpay(payment_id, data)
    return ok(result, "VNPAY QueryDR executed.")


@bp.post("/online")
@jwt_required(optional=True)
def r_create_online_payment():
    data = request.get_json(silent=True) or {}
    session_id = _extract_session_id()
    if session_id and "session_id" not in data:
        data = dict(data)
        data["session_id"] = session_id
    if "ip_addr" not in data:
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        remote = (request.remote_addr or "").strip()
        data = dict(data)
        data["ip_addr"] = forwarded or remote or "127.0.0.1"
    payment = s_create_online_payment(get_jwt_identity(), data)
    return created(payment, "Online payment created successfully.")


@bp.route("/webhook/vnpay", methods=["GET", "POST"])
def r_vnpay_webhook():
    # VNPAY IPN/ReturnUrl can be GET or POST; accept both sources.
    params = request.args.to_dict(flat=True)
    if request.form:
        params.update(request.form.to_dict(flat=True))
    resp_body, status = s_handle_vnpay_webhook(params)
    return resp_body, status


@bp.get("/vnpay/return")
def r_vnpay_return():
    """
    Simple return page for VNPAY sandbox while frontend is not ready.
    Echoes back key VNPAY params (e.g., vnp_ResponseCode, vnp_TxnRef)
    to make debugging easier.
    """
    params = request.args.to_dict(flat=True)

    # Return URL is for browser UX/debugging. Final payment confirmation should come from IPN
    # (or QueryDR reconciliation), not from this route.
    inspected = s_inspect_vnpay_return(params) if params else {}

    txn_ref = inspected.get("txn_ref") or params.get("vnp_TxnRef") or ""
    rsp_code = inspected.get("response_code") or params.get("vnp_ResponseCode") or ""
    txn_status = inspected.get("transaction_status") or params.get("vnp_TransactionStatus") or ""
    signature_valid = inspected.get("signature_valid")
    payment_id = inspected.get("payment_id") or ""
    checkout_id = inspected.get("checkout_id") or ""
    payment_status = inspected.get("payment_status") or ""
    message = (
        "Chu ky callback khong hop le."
        if signature_valid is False
        else (
            "Thanh toan thanh cong (dang cho he thong xac nhan)."
            if (rsp_code == "00" and txn_status in ("", "00"))
            else "Thanh toan that bai hoac dang cho xu ly."
        )
    )

    # If a frontend redirect URL is configured, redirect the browser there with minimal context.
    # The frontend should call the backend to confirm the final payment status.
    redirect_base = os.environ.get("VNPAY_RETURN_REDIRECT_URL")
    if redirect_base:
        status = "success" if (rsp_code == "00" and txn_status in ("", "00")) else ("failed" if rsp_code else "unknown")
        if signature_valid is False:
            status = "invalid_signature"
        split = urlsplit(redirect_base)
        qs = dict(parse_qsl(split.query, keep_blank_values=True))
        qs.update(
            {
                "status": status,
                "payment_id": payment_id,
                "checkout_id": checkout_id,
                "payment_status": payment_status,
                "vnp_TxnRef": txn_ref,
                "vnp_ResponseCode": rsp_code,
                "vnp_TransactionStatus": txn_status,
                "signature_valid": "" if signature_valid is None else str(bool(signature_valid)).lower(),
            }
        )
        target = urlunsplit((split.scheme, split.netloc, split.path, urlencode(qs), split.fragment))
        return redirect(target, code=302)

    html = (
        "<!doctype html>"
        "<html lang='vi'>"
        "<head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Payment processed</title>"
        "</head>"
        "<body>"
        "<h1>Payment processed</h1>"
        f"<p>{message}</p>"
        "<p>(Trang này chỉ dùng tạm cho môi trường sandbox; "
        "trong production sẽ redirect về frontend.)</p>"
        f"<p><strong>vnp_TxnRef:</strong> {txn_ref}</p>"
        f"<p><strong>vnp_ResponseCode:</strong> {rsp_code}</p>"
        f"<p><strong>vnp_TransactionStatus:</strong> {txn_status}</p>"
        f"<p><strong>signature_valid:</strong> {signature_valid}</p>"
        f"<p><strong>local_payment_status:</strong> {payment_status}</p>"
        "</body>"
        "</html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}
