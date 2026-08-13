from __future__ import annotations

import unittest
from uuid import uuid4

from backend.domain.models import HelpPointCategory, Need, NeedStatus


class NeedModelTests(unittest.TestCase):
    def test_active_commitment_count_defaults_to_zero(self) -> None:
        need = Need(id=uuid4(), category_id=uuid4(), status=NeedStatus.NEEDS_HELP)

        self.assertEqual(need.active_commitment_count, 0)


class HelpPointCategoryTests(unittest.TestCase):
    def test_includes_money_donation_category(self) -> None:
        self.assertEqual(HelpPointCategory.MONEY_DONATION.value, "Donación de dinero")

    def test_includes_pet_assistance_category(self) -> None:
        self.assertEqual(
            HelpPointCategory.PET_ASSISTANCE.value, "Ayuda para mascotas"
        )


if __name__ == "__main__":
    unittest.main()
