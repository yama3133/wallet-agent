"""エージェントが「買える」x402 マーチャント候補のカタログ（PoC用）。

PoC では1件だけ。実運用では Coinbase x402 Bazaar や 動的検索ツール経由に置き換える。
"""
from __future__ import annotations

CATALOG = [
    {
        "id": "market-recap",
        "title": "今日の市況サマリ（プレミアム）",
        "description": "NYSE / NASDAQ の今日の主要指数・銘柄動向をプロセプトに整形して返す。",
        "url": "https://drvd12nxpcyd5.cloudfront.net/market-recap",
        "expected_amount_usd": "0.001",
        "expected_currency": "USDC",
        "expected_network": "base-sepolia",
    }
]


def search(query: str | None = None) -> list[dict]:
    """簡易キーワード検索。query=None ならカタログ全件。"""
    if not query:
        return CATALOG
    q = query.lower()
    return [
        r
        for r in CATALOG
        if q in r["title"].lower() or q in r["description"].lower() or q in r["id"].lower()
    ]
