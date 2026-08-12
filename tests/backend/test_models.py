from __future__ import annotations

import unittest
from uuid import uuid4

from backend.domain.models import Need, NeedStatus


class NeedModelTests(unittest.TestCase):
    def test_active_commitment_count_defaults_to_zero(self) -> None:
        need = Need(id=uuid4(), category_id=uuid4(), status=NeedStatus.NEEDS_HELP)

        self.assertEqual(need.active_commitment_count, 0)


if __name__ == "__main__":
    unittest.main()
