"""楽天市場 IchibaItem/Search API ラッパー（Phase 2）。

PoC: 検索のみ。実購入は楽天会員ログイン経由が必要なので、デモでは
Stripe Checkout 経由の擬似決済（商品データだけ楽天から取得）にする想定。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

# 新仕様 (2026-04-01) は openapi.rakuten.co.jp、 旧仕様 (legacy numeric appId) は app.rakuten.co.jp
ENDPOINT_NEW = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
ENDPOINT_LEGACY = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"


def search(
    keyword: str,
    *,
    max_price: int | None = None,
    min_price: int | None = None,
    hits: int = 5,
    sort: str = "-reviewAverage",
) -> list[dict]:
    """楽天市場商品検索。最も評価の高い順に hits 件返す（デフォルト）。

    Returns:
        items: 各要素に id, title, price, image, url, shop, reviewAverage が入る。
    """
    app_id = os.environ.get("RAKUTEN_APPLICATION_ID")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
    if not app_id:
        raise RuntimeError("RAKUTEN_APPLICATION_ID が未設定")

    # UUID 形式 (新仕様) なら openapi、 数字 (旧仕様) なら legacy エンドポイント
    is_new_api = "-" in app_id
    endpoint = ENDPOINT_NEW if is_new_api else ENDPOINT_LEGACY

    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "hits": str(hits),
        "sort": sort,
        "format": "json",
        "formatVersion": "2",
    }
    if max_price is not None:
        params["maxPrice"] = str(max_price)
    if min_price is not None:
        params["minPrice"] = str(min_price)

    referer = os.environ.get("WALLET_AGENT_PUBLIC_URL", "https://wallet-agent.vercel.app/")
    if not referer.endswith("/"):
        referer = referer + "/"
    # 楽天 API の bot ガードを回避するためブラウザ風 UA を使う（OFL 内）
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Referer": referer,
        "Origin": referer.rstrip("/"),
    }
    if access_key:
        headers["accessKey"] = access_key
        params["accessKey"] = access_key

    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())

    out: list[dict] = []
    for it in data.get("Items", []):
        img = (it.get("mediumImageUrls") or [None])[0]
        out.append(
            {
                "id": it.get("itemCode"),
                "title": it.get("itemName"),
                "price": it.get("itemPrice"),
                "currency": "JPY",
                "url": it.get("itemUrl"),
                "image": img,
                "shop": it.get("shopName"),
                "reviewAverage": it.get("reviewAverage"),
            }
        )
    return out
