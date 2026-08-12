from __future__ import annotations

import secrets


class CoordinatorAccessService:
    def __init__(self, expected_key: str) -> None:
        if not expected_key:
            raise ValueError("expected_key must not be empty")

        self._expected_key = expected_key

    def authorize(self, provided_key: str) -> bool:
        if not provided_key:
            return False

        return secrets.compare_digest(self._expected_key, provided_key)
