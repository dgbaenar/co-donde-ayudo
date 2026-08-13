from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Condition, RLock
from time import monotonic
from types import MappingProxyType
from uuid import UUID

from backend.domain.models import PublicHelpPoint


PUBLIC_CACHE_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class CachedPublicHome:
    points: tuple[PublicHelpPoint, ...]
    categories: Mapping[str, UUID]
    stale: bool


@dataclass(frozen=True)
class CachedPublicPoint:
    point: PublicHelpPoint
    categories: Mapping[str, UUID]
    stale: bool


@dataclass(frozen=True)
class RefreshToken:
    generation: int
    sequence: int
    point_id: UUID | None


@dataclass(frozen=True)
class _HomeEntry:
    points: tuple[PublicHelpPoint, ...]
    categories: Mapping[str, UUID]
    stored_at: float


@dataclass(frozen=True)
class _PointEntry:
    point: PublicHelpPoint
    categories: Mapping[str, UUID]
    stored_at: float


@dataclass
class _PointRefreshFlight:
    token: RefreshToken
    waiter_count: int = 0
    completed: bool = False
    committed: bool = False
    result: CachedPublicPoint | None = None
    aborted: bool = False


class PublicHelpPointCache:
    """Thread-safe, process-local cache with stale-while-revalidate reads."""

    def __init__(
        self,
        *,
        ttl_seconds: float = PUBLIC_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = RLock()
        self._condition = Condition(self._lock)
        self._generation = 0
        self._next_sequence = 0
        self._home: _HomeEntry | None = None
        self._points: dict[UUID, _PointEntry] = {}
        self._home_refresh: RefreshToken | None = None
        self._point_refreshes: dict[UUID, _PointRefreshFlight] = {}

    def get_home(self) -> CachedPublicHome | None:
        with self._lock:
            entry = self._home
            if entry is None:
                return None
            return CachedPublicHome(
                points=entry.points,
                categories=entry.categories,
                stale=self._is_stale(entry.stored_at),
            )

    def store_home(
        self,
        points: tuple[PublicHelpPoint, ...],
        categories: Mapping[str, UUID],
    ) -> None:
        stored_at = self._clock()
        immutable_categories = MappingProxyType(dict(categories))
        immutable_points = tuple(points)
        with self._lock:
            self._home = _HomeEntry(
                points=immutable_points,
                categories=immutable_categories,
                stored_at=stored_at,
            )
            self._points = {
                point.id: _PointEntry(
                    point=point,
                    categories=immutable_categories,
                    stored_at=stored_at,
                )
                for point in immutable_points
            }

    def begin_home_refresh(self) -> RefreshToken | None:
        with self._condition:
            if self._home_refresh is not None:
                return None
            token = self._new_token(point_id=None)
            self._home_refresh = token
            return token

    def finish_home_refresh(
        self,
        token: RefreshToken,
        points: tuple[PublicHelpPoint, ...],
        categories: Mapping[str, UUID],
    ) -> bool:
        with self._condition:
            if self._home_refresh != token:
                return False
            committed = token.generation == self._generation
            if committed:
                self.store_home(points, categories)
            self._home_refresh = None
            self._condition.notify_all()
            return committed

    def abort_home_refresh(self, token: RefreshToken) -> None:
        with self._condition:
            if self._home_refresh == token:
                self._home_refresh = None
                self._condition.notify_all()

    def wait_for_home(self, timeout: float) -> CachedPublicHome | None:
        with self._condition:
            if self._home is not None:
                return self.get_home()
            self._condition.wait_for(
                lambda: self._home is not None or self._home_refresh is None,
                timeout=timeout,
            )
            return self.get_home()

    def get_point(self, point_id: UUID) -> CachedPublicPoint | None:
        with self._lock:
            entry = self._points.get(point_id)
            if entry is None:
                return None
            return CachedPublicPoint(
                point=entry.point,
                categories=entry.categories,
                stale=self._is_stale(entry.stored_at),
            )

    def store_point(
        self,
        point: PublicHelpPoint,
        categories: Mapping[str, UUID],
    ) -> CachedPublicPoint:
        entry = _PointEntry(
            point=point,
            categories=MappingProxyType(dict(categories)),
            stored_at=self._clock(),
        )
        with self._lock:
            self._points[point.id] = entry
        return CachedPublicPoint(
            point=entry.point,
            categories=entry.categories,
            stale=False,
        )

    def begin_point_refresh(self, point_id: UUID) -> RefreshToken | None:
        with self._condition:
            flight = self._point_refreshes.get(point_id)
            if flight is not None:
                flight.waiter_count += 1
                return None
            token = self._new_token(point_id=point_id)
            self._point_refreshes[point_id] = _PointRefreshFlight(token=token)
            return token

    def finish_point_refresh(
        self,
        token: RefreshToken,
        point: PublicHelpPoint | None,
        categories: Mapping[str, UUID] | None,
    ) -> tuple[bool, CachedPublicPoint | None]:
        point_id = token.point_id
        if point_id is None:
            raise ValueError("point refresh token is required")
        with self._condition:
            flight = self._point_refreshes.get(point_id)
            if flight is None or flight.token != token:
                if point is None:
                    return False, self.get_point(point_id)
                if categories is None:
                    raise ValueError("categories are required for a public point")
                return False, CachedPublicPoint(
                    point=point,
                    categories=MappingProxyType(dict(categories)),
                    stale=False,
                )
            committed = token.generation == self._generation
            result = None
            if committed:
                if point is None:
                    self._points.pop(point_id, None)
                else:
                    if categories is None:
                        raise ValueError("categories are required for a cached point")
                    result = self.store_point(point, categories)
            flight.completed = True
            flight.committed = committed
            flight.result = result
            if flight.waiter_count == 0:
                self._point_refreshes.pop(point_id, None)
            self._condition.notify_all()
            return committed, result

    def abort_point_refresh(self, token: RefreshToken) -> None:
        point_id = token.point_id
        if point_id is None:
            return
        with self._condition:
            flight = self._point_refreshes.get(point_id)
            if flight is not None and flight.token == token:
                flight.completed = True
                flight.aborted = True
                if flight.waiter_count == 0:
                    self._point_refreshes.pop(point_id, None)
                self._condition.notify_all()

    def wait_for_point_refresh(
        self,
        point_id: UUID,
        timeout: float,
    ) -> tuple[str, CachedPublicPoint | None]:
        with self._condition:
            flight = self._point_refreshes.get(point_id)
            if flight is None:
                return "aborted", self.get_point(point_id)
            finished = self._condition.wait_for(
                lambda: flight.completed,
                timeout=timeout,
            )
            if not finished:
                flight.waiter_count -= 1
                if flight.completed and flight.waiter_count == 0:
                    self._point_refreshes.pop(point_id, None)
                return "timeout", None
            status = "aborted" if flight.aborted or not flight.committed else "completed"
            result = flight.result if status == "completed" else self.get_point(point_id)
            flight.waiter_count -= 1
            if flight.waiter_count == 0:
                self._point_refreshes.pop(point_id, None)
            return status, result

    def remove_point(self, point_id: UUID) -> None:
        with self._lock:
            self._points.pop(point_id, None)

    def clear(self) -> None:
        with self._condition:
            self._generation += 1
            self._home = None
            self._points.clear()
            self._home_refresh = None
            for flight in self._point_refreshes.values():
                flight.completed = True
                flight.aborted = True
            self._point_refreshes.clear()
            self._condition.notify_all()

    def _is_stale(self, stored_at: float) -> bool:
        return self._clock() - stored_at >= self._ttl_seconds

    def _new_token(self, *, point_id: UUID | None) -> RefreshToken:
        self._next_sequence += 1
        return RefreshToken(
            generation=self._generation,
            sequence=self._next_sequence,
            point_id=point_id,
        )
