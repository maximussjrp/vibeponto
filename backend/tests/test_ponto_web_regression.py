"""Regression tests for the web time-clock flow."""

from datetime import datetime

import pytest
from fastapi import HTTPException

from app.api.routes.ponto import _end_date_boundary, _require_web_photo


def test_date_only_end_filter_includes_the_whole_day() -> None:
    boundary, exclusive = _end_date_boundary(datetime(2026, 9, 23))

    assert boundary == datetime(2026, 9, 24)
    assert exclusive is True


def test_timestamp_end_filter_keeps_the_exact_instant() -> None:
    value = datetime(2026, 9, 23, 17, 30)

    boundary, exclusive = _end_date_boundary(value)

    assert boundary == value
    assert exclusive is False


@pytest.mark.parametrize("value", [None, ""])
def test_web_registration_requires_a_photo(value: str | None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _require_web_photo(value)

    assert exc_info.value.status_code == 400
    assert "foto" in str(exc_info.value.detail).lower()
