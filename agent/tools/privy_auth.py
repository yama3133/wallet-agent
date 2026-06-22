"""Privy REST API 用 authorization signature を生成する。

仕様（Privy Go SDK / docs を参照）:
  1. WalletApiRequestSignatureInput を JSON 化
  2. RFC 8785 JSON Canonicalization Scheme (JCS) で正規化
  3. SHA-256 でハッシュ
  4. ECDSA P-256 で署名
  5. DER エンコード
  6. base64 エンコード
"""
from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_private_key


def _canonical_json(obj: Any) -> bytes:
    """RFC 8785 JCS の最小実装。Privy が受け付ける範囲では十分。"""
    return json.dumps(
        obj,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def format_request(
    *,
    method: str,
    url: str,
    body: Any | None,
    app_id: str,
    version: int = 1,
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    headers = {"privy-app-id": app_id}
    if extra_headers:
        headers.update(extra_headers)
    payload: dict[str, Any] = {
        "version": version,
        "method": method.upper(),
        "url": url,
        "headers": headers,
    }
    if body is not None:
        payload["body"] = body
    return _canonical_json(payload)


def generate_authorization_signature(
    *,
    private_key_b64: str,
    payload: bytes,
) -> str:
    """base64(PKCS#8 DER P-256) の秘密鍵で payload に署名し base64(DER) を返す。"""
    der = base64.b64decode(private_key_b64)
    key = load_der_private_key(der, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise RuntimeError("expected EC private key")
    der_sig = key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(der_sig).decode("ascii")


def sign_request(
    *,
    method: str,
    url: str,
    body: Any | None,
    app_id: str,
    private_key_b64: str,
) -> tuple[bytes, str]:
    """(payload_bytes, base64_signature) を返す。"""
    payload = format_request(method=method, url=url, body=body, app_id=app_id)
    sig = generate_authorization_signature(private_key_b64=private_key_b64, payload=payload)
    return payload, sig
