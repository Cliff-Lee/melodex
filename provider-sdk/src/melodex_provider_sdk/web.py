from __future__ import annotations

import gzip
import hashlib
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WebResponse:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        match = re.search(r"charset=([^; ]+)", content_type, flags=re.I)
        encoding = match.group(1).strip('"\'') if match else "utf-8"
        return self.body.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)

    def xml(self) -> ET.Element:
        return ET.fromstring(self.body)


class WebSession:
    """Small stdlib HTTP session for provider adapters."""

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        retries: int = 2,
        min_interval: float = 0.0,
    ) -> None:
        self.base_url = base_url
        self.headers = dict(headers or {})
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.min_interval = max(0.0, float(min_interval))
        self._last_request = 0.0
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )

    def request(
        self,
        method: str,
        url: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> WebResponse:
        target = absolute_url(self.base_url, url)
        request_headers = {**self.headers, **dict(headers or {})}
        request_headers.setdefault("Accept-Encoding", "gzip")
        error: Exception | None = None
        for attempt in range(self.retries + 1):
            delay = self.min_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            req = urllib.request.Request(
                target,
                data=data,
                headers=request_headers,
                method=method.upper(),
            )
            try:
                with self._opener.open(req, timeout=self.timeout) as response:
                    self._last_request = time.monotonic()
                    body = response.read()
                    response_headers = {
                        str(key).casefold(): str(value)
                        for key, value in response.headers.items()
                    }
                    if response_headers.get("content-encoding", "").casefold() == "gzip":
                        body = gzip.decompress(body)
                    return WebResponse(
                        url=str(response.geturl()),
                        status=int(response.status),
                        headers=response_headers,
                        body=body,
                    )
            except Exception as exc:
                error = exc
                if attempt < self.retries:
                    time.sleep(min(2.0**attempt, 4.0))
        assert error is not None
        raise error

    def get(self, url: str, headers: dict[str, str] | None = None) -> WebResponse:
        return self.request("GET", url, headers=headers)

    def post_form(
        self,
        url: str,
        fields: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> WebResponse:
        body = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
        merged = {
            "Content-Type": "application/x-www-form-urlencoded",
            **dict(headers or {}),
        }
        return self.request("POST", url, data=body, headers=merged)


def absolute_url(base: str, value: str) -> str:
    return urllib.parse.urljoin(base, value)


def opaque_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def first_of(data: dict[str, Any], paths: Iterable[str], default: Any = None) -> Any:
    for path in paths:
        value: Any = data
        found = True
        for part in str(path).split("."):
            if not isinstance(value, dict) or part not in value:
                found = False
                break
            value = value[part]
        if found and value not in {None, ""}:
            return value
    return default


def extract_first(text: str, patterns: Iterable[str], default: str = "") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return str(match.group(1) if match.groups() else match.group(0)).strip()
    return default
