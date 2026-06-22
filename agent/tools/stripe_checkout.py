"""Stripe Checkout Session 作成（Phase 2）。

テストモードで動かす想定。APIキーは STRIPE_SECRET_KEY (sk_test_...) を使う。
SDK は使わず urllib で直接 REST を叩く（依存を減らすため）。
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
import urllib.error
import json
import base64


API = "https://api.stripe.com/v1"


def _auth_header() -> dict[str, str]:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY が未設定")
    enc = base64.b64encode((key + ":").encode()).decode()
    return {"Authorization": f"Basic {enc}"}


def _post(path: str, form: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        API + path,
        data=body,
        headers={
            **_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "wallet-agent/0.1 (Phase2 Stripe)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Stripe HTTP {e.code}: {body[:500]}") from e


def create_checkout(
    *,
    title: str,
    amount_jpy: int,
    success_url: str,
    cancel_url: str,
    image_url: str | None = None,
) -> dict:
    """指定商品で Stripe Checkout Session を作成し URL を返す。"""
    form: dict[str, str] = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "jpy",
        "line_items[0][price_data][unit_amount]": str(amount_jpy),
        "line_items[0][price_data][product_data][name]": title[:250],
    }
    if image_url:
        form["line_items[0][price_data][product_data][images][0]"] = image_url
    r = _post("/checkout/sessions", form)
    return {
        "id": r.get("id"),
        "url": r.get("url"),
        "status": r.get("status"),
        "amount_total": r.get("amount_total"),
        "currency": r.get("currency"),
    }
