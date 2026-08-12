import pytest

from backend.application.coordinator_access import CoordinatorAccessService


def test_rejects_an_empty_expected_key() -> None:
    with pytest.raises(ValueError):
        CoordinatorAccessService(expected_key="")


@pytest.mark.parametrize(
    ("provided_key", "authorized"),
    [
        ("", False),
        ("not-the-coordinator-key", False),
        ("coordinator-test-key", True),
    ],
)
def test_authorizes_only_the_exact_expected_key(
    provided_key: str, authorized: bool
) -> None:
    service = CoordinatorAccessService(expected_key="coordinator-test-key")

    assert service.authorize(provided_key) is authorized
