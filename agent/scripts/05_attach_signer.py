"""Step 5: Privy REST API で wallet に Authorization Key を additional signer として追加。

これで AWS の ProcessPayment が Privy walletで署名できるようになるはず。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import urllib.request
import urllib.error

# tools/ を import path に
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import privy_auth  # noqa: E402

from _common import env, print_header, require_state


def main() -> None:
    print_header("Step 5: Privy wallet に Authorization Key を additional signer として追加")

    app_id = env("PRIVY_APP_ID")
    app_secret = env("PRIVY_APP_SECRET")
    signer_id = env("PRIVY_AUTHORIZATION_ID")
    private_key_b64 = env("PRIVY_AUTHORIZATION_PRIVATE_KEY")

    # Privy 側の wallet ID（state.json には walletAddress しか保存していない）
    # Privy ダッシュボードから確認した値を環境変数 PRIVY_WALLET_ID で上書き可能。
    wallet_id = os.environ.get("PRIVY_WALLET_ID") or require_state("privy_wallet_id")

    url = f"https://api.privy.io/v1/wallets/{wallet_id}"
    body = {"additional_signers": [{"signer_id": signer_id}]}
    payload, sig = privy_auth.sign_request(
        method="PATCH", url=url, body=body, app_id=app_id, private_key_b64=private_key_b64
    )
    print(f"signed payload (head): {payload[:120].decode()!r}...")
    print(f"signature (head)     : {sig[:30]}...")

    creds = (app_id + ":" + app_secret).encode()
    import base64

    auth = base64.b64encode(creds).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "privy-app-id": app_id,
        "privy-authorization-signature": sig,
        "Content-Type": "application/json",
        "User-Agent": "wallet-agent/0.1 (+https://github.com/yama3133/wallet-agent)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PATCH", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"\n{r.status} OK")
            print(r.read().decode()[:1000])
    except urllib.error.HTTPError as e:
        print(f"\nHTTP {e.code} {e.reason}")
        print(e.read().decode()[:1000])
        raise


if __name__ == "__main__":
    main()
