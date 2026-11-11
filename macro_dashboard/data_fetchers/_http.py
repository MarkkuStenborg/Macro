# ============================================================================
# File: macro_dashboard/data_fetchers/_http.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\data_fetchers\_http.py
"""Jaettu HTTP-kerros: levyvälimuisti, kutsuväli (rate limit) ja uudelleenyritys.

* Välimuisti: onnistuneet (HTTP 200) vastaukset tallennetaan tekstinä
  ``cache_dir``-kansioon ``ttl_seconds`` ajaksi. Salaiset parametrit
  (``api_key``) EIVÄT ole välimuistiavaimessa eivätkä tallennu levylle.
* ``min_interval``: vähimmäisaika peräkkäisten oikeiden HTTP-kutsujen välillä
  (välimuistiosumat eivät kuluta kutsuväliä).
* Uudelleenyritys: 429/5xx ja verkkovirheet, eksponentiaalinen viive;
  ``Retry-After``-otsikkoa noudatetaan.
* Virheviesteistä poistetaan salaiset arvot.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import requests

from .base import FetchError

__all__ = ["HttpClient"]

_RETRY_STATUS = {429, 500, 502, 503, 504}


class _CachedResponse:
    status_code = 200
    headers: Mapping[str, str] = {}

    def __init__(self, text: str) -> None:
        self.text = text

    def json(self) -> Any:
        return json.loads(self.text)


class HttpClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        cache_dir: str | Path | None = None,
        ttl_seconds: float = 3600.0,
        min_interval: float = 0.0,
        retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 30.0,
        user_agent: str = "macro_dashboard/0.1",
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session or requests.Session()
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._min_interval = min_interval
        self._retries = retries
        self._backoff = backoff
        self._timeout = timeout
        self._user_agent = user_agent
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    # -- julkinen ----------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        secret_params: Iterable[str] = ("api_key",),
    ):
        return self._request("GET", url, params, headers, None, tuple(secret_params))

    def post(
        self,
        url: str,
        *,
        json_body: Any,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        return self._request("POST", url, params, headers, json_body, ())

    # -- sisäiset ------------------------------------------------------------

    def _cache_path(self, method, url, params, headers, body, secret) -> Path:
        public = {k: v for k, v in (params or {}).items() if k not in secret}
        accept = (headers or {}).get("Accept", "")
        raw = json.dumps(
            [method, url, sorted(public.items()), accept, body], sort_keys=True, default=str
        )
        assert self._cache_dir is not None
        return self._cache_dir / (hashlib.sha256(raw.encode("utf-8")).hexdigest() + ".txt")

    def _throttle(self) -> None:
        if self._min_interval > 0 and self._last_request is not None:
            wait = self._last_request + self._min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _retry_delay(self, resp: Any, attempt: int) -> float:
        retry_after = (getattr(resp, "headers", None) or {}).get("Retry-After")
        try:
            return float(retry_after) if retry_after is not None else self._backoff**attempt
        except ValueError:
            return self._backoff**attempt

    @staticmethod
    def _scrub(text: str, params: Mapping[str, Any] | None, secret: Iterable[str]) -> str:
        for key in secret:
            value = (params or {}).get(key)
            if value:
                text = text.replace(str(value), "***")
        return text

    def _request(self, method, url, params, headers, body, secret):
        hdrs = {"User-Agent": self._user_agent, **(headers or {})}
        path = self._cache_path(method, url, params, hdrs, body, secret) if self._cache_dir else None
        if path is not None and path.exists() and time.time() - path.stat().st_mtime < self._ttl:
            return _CachedResponse(path.read_text(encoding="utf-8"))

        resp = None
        for attempt in range(self._retries + 1):
            self._throttle()
            try:
                resp = self._session.request(
                    method, url, params=params, headers=hdrs, json=body, timeout=self._timeout
                )
            except requests.RequestException as exc:
                if attempt == self._retries:
                    msg = self._scrub(str(exc), params, secret)
                    raise FetchError(f"Yhteys epäonnistui ({url}): {msg}") from None
                self._sleep(self._backoff**attempt)
                continue
            if resp.status_code in _RETRY_STATUS and attempt < self._retries:
                self._sleep(self._retry_delay(resp, attempt))
                continue
            break

        if path is not None and resp is not None and resp.status_code == 200:
            path.write_text(resp.text, encoding="utf-8")
        return resp
