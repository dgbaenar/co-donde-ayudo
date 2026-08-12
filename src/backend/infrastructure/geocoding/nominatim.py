from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    latitude: float
    longitude: float


def open_request(request: Request) -> Any:
    return urlopen(request, timeout=5.0)


class NominatimRateLimiter:
    def __init__(
        self,
        *,
        interval_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            if self._last_request_at is not None:
                remaining = self._interval_seconds - (
                    self._clock() - self._last_request_at
                )
                if remaining > 0:
                    await self._sleep(remaining)
            self._last_request_at = self._clock()


_DEFAULT_RATE_LIMITER = NominatimRateLimiter()


class NominatimGeocoder:
    _ENDPOINT = "https://nominatim.openstreetmap.org/search"
    _USER_AGENT = "DondeAyudo/0.1"

    def __init__(
        self,
        *,
        request: Callable[[Request], Any] = open_request,
        rate_limiter: NominatimRateLimiter | None = None,
    ) -> None:
        self._request = request
        self._rate_limiter = rate_limiter or _DEFAULT_RATE_LIMITER

    async def search(
        self, address: str, city: str, department: str
    ) -> GeocodedLocation | None:
        request = Request(
            self._search_url(address, city, department),
            headers={"User-Agent": self._USER_AGENT},
        )

        await self._rate_limiter.wait()

        try:
            payload = await asyncio.to_thread(self._read_response, request)
            match = json.loads(payload)[0]
            latitude = float(match["lat"])
            longitude = float(match["lon"])
            if not (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                return None
            return GeocodedLocation(latitude=latitude, longitude=longitude)
        except Exception:
            return None

    @classmethod
    def _search_url(cls, address: str, city: str, department: str) -> str:
        query = ", ".join(
            part for part in (address, city, department, "Colombia") if part
        )
        parameters = {
            "q": query,
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "co",
            "accept-language": "es",
        }
        return f"{cls._ENDPOINT}?{urlencode(parameters)}"

    def _read_response(self, request: Request) -> bytes:
        with self._request(request) as response:
            return response.read()
