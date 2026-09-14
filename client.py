"""
Thin Attio REST client: auth, retries with backoff, and webhook signature
validation. No business logic here — that lives in queries.py and
recommendations/engine.py.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

ATTIO_API_BASE = "https://api.attio.com/v2"


class AttioConfigError(RuntimeError):
    pass


class AttioAPIError(RuntimeError):
    def __init__(self, status_code: int, body: Any):
        super().__init__(f"Attio API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def _env() -> str:
    return os.environ.get("RM_ENV", "development").strip().lower()


def _token_for_env(env: str) -> str:
    var = f"ATTIO_API_TOKEN_{env.upper()}"
    token = os.environ.get(var, "").strip()
    if not token:
        raise AttioConfigError(
            f"Missing {var}. Set it in your deployment secret manager "
            f"before running against '{env}'."
        )
    return token


class AttioClient:
    """
    Environment is read from RM_ENV so that pointing this at production
    requires deliberately setting RM_ENV=production, not just having a
    production token lying around in the environment.
    """

    def __init__(self, env: str | None = None, max_retries: int | None = None):
        self.env = (env or _env()).strip().lower()
        self.token = _token_for_env(self.env)
        self.max_retries = max_retries or int(os.environ.get("RM_MAX_RETRIES", "5"))
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{ATTIO_API_BASE}{path}"
        backoff = 1.0
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Attio request failed (attempt %s): %s", attempt, exc)
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(
                    "Attio %s %s -> %s, retrying (attempt %s)",
                    method,
                    path,
                    resp.status_code,
                    attempt,
                )
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code >= 400:
                raise AttioAPIError(resp.status_code, _safe_body(resp))

            return _safe_body(resp)

        raise AttioAPIError(-1, f"exhausted retries: {last_error}")

    def query_records(self, object_slug: str, body: dict) -> Any:
        return self._request("POST", f"/objects/{object_slug}/records/query", json=body)

    def get_record(self, object_slug: str, record_id: str) -> Any:
        return self._request("GET", f"/objects/{object_slug}/records/{record_id}")

    def update_record(self, object_slug: str, record_id: str, attributes: dict) -> Any:
        return self._request(
            "PATCH",
            f"/objects/{object_slug}/records/{record_id}",
            json={"data": {"values": attributes}},
        )

    def create_note(self, record_id: str, object_slug: str, content: str, title: str = "") -> Any:
        return self._request(
            "POST",
            "/notes",
            json={
                "data": {
                    "parent_object": object_slug,
                    "parent_record_id": record_id,
                    "title": title,
                    "content": content,
                    "format": "plaintext",
                }
            },
        )


def _safe_body(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def verify_webhook_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """
    Constant-time HMAC-SHA256 verification for inbound Attio/Mailchimp-style
    webhooks. Callers must reject the request if this returns False.
    """
    if not signature_header or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
