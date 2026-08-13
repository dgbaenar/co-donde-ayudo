from __future__ import annotations

import threading
import unittest
from uuid import UUID

from backend.application.public_cache import PublicHelpPointCache


class PublicHelpPointCacheConcurrencyTests(unittest.TestCase):
    def test_home_refresh_is_single_flight_and_waiter_receives_completed_entry(self) -> None:
        cache = PublicHelpPointCache()
        token = cache.begin_home_refresh()
        self.assertIsNotNone(token)
        self.assertIsNone(cache.begin_home_refresh())
        received = []

        waiter = threading.Thread(
            target=lambda: received.append(cache.wait_for_home(timeout=1.0))
        )
        waiter.start()
        self.assertTrue(cache.finish_home_refresh(token, (), {"Agua": UUID(int=1)}))
        waiter.join(timeout=1.0)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(len(received), 1)
        self.assertEqual(dict(received[0].categories), {"Agua": UUID(int=1)})

    def test_invalidation_prevents_in_flight_home_refresh_from_repopulating_cache(self) -> None:
        cache = PublicHelpPointCache()
        token = cache.begin_home_refresh()

        cache.clear()
        committed = cache.finish_home_refresh(token, (), {"Agua": UUID(int=1)})

        self.assertFalse(committed)
        self.assertIsNone(cache.get_home())

    def test_aborting_home_refresh_wakes_cold_waiters_without_data(self) -> None:
        cache = PublicHelpPointCache()
        token = cache.begin_home_refresh()
        received = []
        waiter = threading.Thread(
            target=lambda: received.append(cache.wait_for_home(timeout=1.0))
        )
        waiter.start()

        cache.abort_home_refresh(token)
        waiter.join(timeout=1.0)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(received, [None])

    def test_completed_missing_point_refreshes_do_not_accumulate_coordination_state(
        self,
    ) -> None:
        cache = PublicHelpPointCache()

        for value in range(1, 101):
            token = cache.begin_point_refresh(UUID(int=value))
            committed, result = cache.finish_point_refresh(token, None, None)
            self.assertTrue(committed)
            self.assertIsNone(result)

        self.assertEqual(cache._point_refreshes, {})
        self.assertFalse(hasattr(cache, "_completed_point_refreshes"))

    def test_all_registered_point_waiters_receive_same_missing_result_before_cleanup(
        self,
    ) -> None:
        cache = PublicHelpPointCache()
        point_id = UUID(int=1)
        token = cache.begin_point_refresh(point_id)
        self.assertIsNone(cache.begin_point_refresh(point_id))
        self.assertIsNone(cache.begin_point_refresh(point_id))
        received = []
        waiters = [
            threading.Thread(
                target=lambda: received.append(
                    cache.wait_for_point_refresh(point_id, timeout=1.0)
                )
            )
            for _ in range(2)
        ]
        for waiter in waiters:
            waiter.start()

        committed, result = cache.finish_point_refresh(token, None, None)
        for waiter in waiters:
            waiter.join(timeout=1.0)

        self.assertTrue(committed)
        self.assertIsNone(result)
        self.assertTrue(all(not waiter.is_alive() for waiter in waiters))
        self.assertEqual(received, [("completed", None), ("completed", None)])
        self.assertEqual(cache._point_refreshes, {})
        self.assertFalse(hasattr(cache, "_completed_point_refreshes"))
