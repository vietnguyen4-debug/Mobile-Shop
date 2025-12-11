"""
Utility script to generate a VNPAY sandbox payment URL without touching the app.

Usage (from repo root, venv optional):
  # Option 1: supply amount + txn-ref directly
  python tools/gen_vnpay_url.py --amount 100000 --txn-ref 64e9... \
    --order-info "Thanh toan don hang"

  # Option 2: derive amount/txn-ref from an existing payment via API
  python tools/gen_vnpay_url.py --payment-id 64e9... --api-base http://localhost:5000/api

Env required:
  VNPAY_TMN_CODE, VNPAY_SECRET_KEY, VNPAY_PAYMENT_URL, VNPAY_RETURN_URL, VNPAY_IPN_URL
"""

import argparse
import datetime
import hmac
import hashlib
import os
import sys
import urllib.parse
from dotenv import load_dotenv
import httpx


def _now_vn():
    tz = datetime.timezone(datetime.timedelta(hours=7))
    return datetime.datetime.now(tz)


def build_vnpay_url(*, tmn_code, secret, payment_url, return_url, ipn_url, amount, txn_ref, order_info):
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": int(amount * 100),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": order_info or "Thanh toan don hang",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url,
        "vnp_IpnUrl": ipn_url,
        "vnp_CreateDate": _now_vn().strftime("%Y%m%d%H%M%S"),
    }
    items = sorted(params.items())
    raw = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in items)
    secure_hash = hmac.new(secret.encode(), raw.encode(), hashlib.sha512).hexdigest().upper()
    params["vnp_SecureHashType"] = "HMACSHA512"
    params["vnp_SecureHash"] = secure_hash
    query = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items())
    return f"{payment_url}?{query}"


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate VNPAY sandbox payment URL.")
    parser.add_argument("--amount", type=float, help="Amount in VND (e.g., 100000)")
    parser.add_argument("--txn-ref", help="vnp_TxnRef to use (e.g., provider_ref or payment id)")
    parser.add_argument("--payment-id", help="Fetch amount/txn_ref from API payment id (overrides --amount/--txn-ref)")
    parser.add_argument("--api-base", default="http://localhost:5000/api", help="API base URL to fetch payment (http/https required)")
    parser.add_argument("--session-id", help="Session id (for guest payments) sent as Cookie session_id=<id>")
    parser.add_argument("--order-info", default="Thanh toan don hang", help="Order info text")
    args = parser.parse_args()

    tmn_code = os.environ.get("VNPAY_TMN_CODE")
    secret = os.environ.get("VNPAY_SECRET_KEY")
    payment_url = os.environ.get("VNPAY_PAYMENT_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
    return_url = os.environ.get("VNPAY_RETURN_URL")
    ipn_url = os.environ.get("VNPAY_IPN_URL")

    missing = [k for k, v in [("VNPAY_TMN_CODE", tmn_code), ("VNPAY_SECRET_KEY", secret), ("VNPAY_RETURN_URL", return_url), ("VNPAY_IPN_URL", ipn_url)] if not v]
    if missing:
        sys.stderr.write(f"Missing env: {', '.join(missing)}\n")
        sys.exit(1)

    amount = args.amount
    txn_ref = args.txn_ref

    if args.payment_id:
        base = args.api_base
        if not base.startswith(("http://", "https://")):
            base = "https://" + base.lstrip("/")
        url = f"{base.rstrip('/')}/payments/{args.payment_id}"
        headers = {}
        if args.session_id:
            headers["Cookie"] = f"session_id={args.session_id}"
        try:
            resp = httpx.get(url, timeout=10.0, headers=headers)
        except Exception as exc:
            sys.stderr.write(f"Failed to fetch payment: {exc}\n")
            sys.exit(1)
        if resp.status_code >= 400:
            sys.stderr.write(
                f"Failed to fetch payment: HTTP {resp.status_code}\n{resp.text}\n"
            )
            sys.exit(1)
        payload = resp.json().get("data") or {}
        amount = float(payload.get("amount") or 0)
        txn_ref = payload.get("provider_ref") or payload.get("id")
        if amount <= 0 or not txn_ref:
            sys.stderr.write("Payment data missing amount/txn_ref\n")
            sys.exit(1)
    if amount is None or txn_ref is None:
        sys.stderr.write("Either provide --payment-id or both --amount and --txn-ref\n")
        sys.exit(1)

    url = build_vnpay_url(
        tmn_code=tmn_code,
        secret=secret,
        payment_url=payment_url,
        return_url=return_url,
        ipn_url=ipn_url,
        amount=amount,
        txn_ref=txn_ref,
        order_info=args.order_info,
    )
    print(url)


if __name__ == "__main__":
    main()
