from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from backend.infrastructure.geocoding.nominatim import (
    GeocodedLocation,
    NominatimGeocoder,
    NominatimRateLimiter,
)


class Response:
    def __init__(self, payload: str) -> None:
        self._payload = payload.encode("utf-8")

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class RecordingRequest:
    def __init__(
        self,
        payload: str = '[{"lat":"3.4372","lon":"-76.5225"}]',
        *,
        error: Exception | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._payload = payload
        self._error = error
        self._clock = clock
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}
        self.called_at: list[float] = []

    def __call__(self, request: Request) -> Response:
        self.urls.append(request.full_url)
        self.headers = dict(request.header_items())
        if self._clock is not None:
            self.called_at.append(self._clock())
        if self._error is not None:
            raise self._error
        return Response(self._payload)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def geocoder(
    *,
    request: RecordingRequest,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> NominatimGeocoder:
    resolved_clock = clock or (lambda: 0.0)
    resolved_sleep = sleep or asyncio.sleep
    return NominatimGeocoder(
        request=request,
        rate_limiter=NominatimRateLimiter(
            clock=resolved_clock,
            sleep=resolved_sleep,
        ),
    )


def test_search_limits_query_to_colombia_and_identifies_application() -> None:
    request = RecordingRequest()

    result = asyncio.run(
        geocoder(request=request).search(
            "Calle 5 # 10-20", "Cali", "Valle del Cauca"
        )
    )

    assert result == GeocodedLocation(
        latitude=3.4372, longitude=-76.5225, is_low_confidence=True
    )
    query = parse_qs(urlparse(request.urls[0]).query)
    assert query["countrycodes"] == ["co"]
    assert query["limit"] == ["1"]
    assert query["format"] == ["jsonv2"]
    assert query["accept-language"] == ["es"]
    assert query["q"] == ["Calle 5 # 10-20, Cali, Valle del Cauca, Colombia"]
    assert request.headers["User-agent"].startswith("DondeAyudo/")


def test_search_returns_none_when_provider_has_no_match() -> None:
    result = asyncio.run(geocoder(request=RecordingRequest("[]")).search("", "Cali", ""))

    assert result is None


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '[{"lat":"not-a-number","lon":"-76.5225"}]',
        '[{"lat":"NaN","lon":"-76.5225"}]',
        '[{"lat":"Infinity","lon":"-76.5225"}]',
        '[{"lat":"91","lon":"-76.5225"}]',
        '[{"lat":"3.4372","lon":"-181"}]',
    ],
)
def test_search_returns_none_for_invalid_provider_payload(payload: str) -> None:
    result = asyncio.run(geocoder(request=RecordingRequest(payload)).search("", "Cali", ""))

    assert result is None


def test_search_returns_none_when_request_fails() -> None:
    result = asyncio.run(
        geocoder(request=RecordingRequest(error=OSError("synthetic failure"))).search(
            "", "Cali", ""
        )
    )

    assert result is None


def test_search_spaces_requests_one_second_apart() -> None:
    clock = Clock()
    request = RecordingRequest(clock=clock)
    adapter = geocoder(request=request, clock=clock, sleep=clock.sleep)

    async def search_twice() -> None:
        await adapter.search("", "Cali", "")
        await adapter.search("", "Cali", "")

    asyncio.run(search_twice())

    assert request.called_at == [0.0, 1.0]
    assert clock.sleeps == [1.0]


def test_two_instances_share_an_injected_limiter_under_concurrency() -> None:
    request = RecordingRequest(clock=time.monotonic)
    limiter = NominatimRateLimiter(interval_seconds=0.02)
    first = NominatimGeocoder(request=request, rate_limiter=limiter)
    second = NominatimGeocoder(request=request, rate_limiter=limiter)

    async def search_concurrently() -> None:
        await asyncio.gather(
            first.search("", "Cali", ""),
            second.search("", "Cali", ""),
        )

    asyncio.run(search_concurrently())

    assert len(request.called_at) == 2
    assert request.called_at[1] - request.called_at[0] >= 0.018


def test_search_marks_high_importance_match_as_not_low_confidence() -> None:
    payload = '[{"lat":"3.4372","lon":"-76.5225","importance":"0.8"}]'

    result = asyncio.run(
        geocoder(request=RecordingRequest(payload)).search(
            "Calle 5 # 10-20", "Cali", "Valle del Cauca"
        )
    )

    assert result == GeocodedLocation(
        latitude=3.4372, longitude=-76.5225, is_low_confidence=False
    )


@pytest.mark.parametrize(
    "payload",
    [
        '[{"lat":"3.4372","lon":"-76.5225","importance":"0.1"}]',
        '[{"lat":"3.4372","lon":"-76.5225"}]',
    ],
)
def test_search_flags_low_or_missing_importance_as_low_confidence(payload: str) -> None:
    result = asyncio.run(
        geocoder(request=RecordingRequest(payload)).search(
            "Calle 5 # 10-20", "Cali", "Valle del Cauca"
        )
    )

    assert result == GeocodedLocation(
        latitude=3.4372, longitude=-76.5225, is_low_confidence=True
    )


def test_default_request_uses_a_short_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, float] = {}

    def fake_urlopen(request: Request, *, timeout: float) -> Response:
        captured["timeout"] = timeout
        return Response('[{"lat":"3.4372","lon":"-76.5225"}]')

    monkeypatch.setattr(
        "backend.infrastructure.geocoding.nominatim.urlopen",
        fake_urlopen,
    )
    adapter = NominatimGeocoder(
        rate_limiter=NominatimRateLimiter(
            clock=lambda: 0.0,
            sleep=asyncio.sleep,
        )
    )

    result = asyncio.run(adapter.search("Calle 5", "Cali", "Valle del Cauca"))

    assert result == GeocodedLocation(
        latitude=3.4372, longitude=-76.5225, is_low_confidence=True
    )
    assert captured["timeout"] == 5.0
