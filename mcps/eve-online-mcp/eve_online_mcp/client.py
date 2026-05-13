from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

import httpx

DEFAULT_ESI_BASE = "https://esi.evetech.net/latest"
DEFAULT_DATASOURCE = "tranquility"

class EsiApiError(RuntimeError):
    """Raised when ESI returns a non-success response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})


def _esi_base() -> str:
    return (os.getenv("EVE_ESI_BASE_URL") or DEFAULT_ESI_BASE).rstrip("/")


def _datasource() -> str:
    return os.getenv("EVE_ESI_DATASOURCE", DEFAULT_DATASOURCE)


def _timeout() -> float:
    raw = os.getenv("EVE_ESI_TIMEOUT", "30")
    try:
        return float(raw)
    except ValueError:
        return 30.0


def _compatibility_date() -> str:
    configured = os.getenv("EVE_ESI_COMPATIBILITY_DATE")
    if configured:
        return configured
    return (datetime.now(timezone.utc) - timedelta(hours=11)).date().isoformat()


def _clean_positive_int(value: int, field_name: str) -> int:
    if value < 1:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value


def _clean_page(value: int) -> int:
    if not (1 <= value <= 10000):
        raise ValueError("page must be between 1 and 10000.")
    return value


def _clean_limit(value: int, field_name: str, max_value: int) -> int:
    if not (1 <= value <= max_value):
        raise ValueError(f"{field_name} must be between 1 and {max_value}.")
    return value


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a YYYY-MM-DD date, got {value!r}.") from exc


def _omit_none(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _esi_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "eve-online-mcp/0.1.0",
        "X-Compatibility-Date": _compatibility_date(),
    }
    headers.update(extra or {})
    return headers


def _response_headers(response: httpx.Response) -> dict[str, str]:
    interesting = {
        "cache-control",
        "etag",
        "expires",
        "last-modified",
        "retry-after",
        "x-compatibility-date",
        "x-esi-error-limit-remain",
        "x-esi-error-limit-reset",
        "x-pages",
        "x-ratelimit-group",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-used",
    }
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in interesting
    }


def _ok(data: Any, response: httpx.Response | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "data": data}
    if response is not None:
        payload["meta"] = {
            "status_code": response.status_code,
            "headers": _response_headers(response),
        }
    return payload


def _error(exc: EsiApiError | Exception) -> dict[str, Any]:
    if isinstance(exc, EsiApiError):
        return {
            "ok": False,
            "error": str(exc),
            "status_code": exc.status_code,
            "body": exc.body,
            "headers": exc.headers,
        }
    return {"ok": False, "error": str(exc)}


_HTTP_CLIENT: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=_timeout())
    return _HTTP_CLIENT


_ESI_ERROR_LIMIT_REMAIN: int = 100
_ESI_ERROR_LIMIT_RESET: int = 60


def _reset_error_limit():
    global _ESI_ERROR_LIMIT_REMAIN, _ESI_ERROR_LIMIT_RESET
    _ESI_ERROR_LIMIT_REMAIN = 100
    _ESI_ERROR_LIMIT_RESET = 60


async def _request(
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[Any, httpx.Response]:
    global _ESI_ERROR_LIMIT_REMAIN, _ESI_ERROR_LIMIT_RESET

    if _ESI_ERROR_LIMIT_REMAIN < 10:
        raise EsiApiError(
            f"ESI error limit almost exhausted ({_ESI_ERROR_LIMIT_REMAIN} remain). "
            f"Backing off for {_ESI_ERROR_LIMIT_RESET} seconds.",
            status_code=429,
        )

    request_params = {"datasource": _datasource(), **dict(params or {})}
    url = f"{_esi_base()}/{path.lstrip('/')}"
    client = _get_client()
    response = await client.request(
        method.upper(),
        url,
        params=_omit_none(request_params),
        json=body,
        headers=_esi_headers(headers),
    )

    # Update error limit tracking
    remain = response.headers.get("x-esi-error-limit-remain")
    reset = response.headers.get("x-esi-error-limit-reset")
    if remain:
        _ESI_ERROR_LIMIT_REMAIN = int(remain)
    if reset:
        _ESI_ERROR_LIMIT_RESET = int(reset)

    if response.status_code == 304:
        return None, response

    try:
        data = response.json()
    except ValueError:
        data = response.text

    if response.status_code >= 400:
        message = data.get("error") if isinstance(data, dict) else response.text
        raise EsiApiError(
            f"ESI returned HTTP {response.status_code} for {method.upper()} {path}: {message}",
            status_code=response.status_code,
            body=data,
            headers=_response_headers(response),
        )

    return data, response


async def _get(path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        data, response = await _request("GET", path, params=params)
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


async def _post(path: str, body: Any, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        data, response = await _request("POST", path, params=params, body=body)
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)
