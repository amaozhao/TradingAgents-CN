from datetime import datetime

from app.routers.analysisrouter import _coerce_datetime


def test_coerce_datetime_accepts_iso_zulu_string_as_naive_utc():
    value = _coerce_datetime("2026-06-03T05:41:27Z")

    assert value == datetime(2026, 6, 3, 5, 41, 27)
    assert value.tzinfo is None


def test_coerce_datetime_accepts_offset_string_as_naive_utc():
    value = _coerce_datetime("2026-06-03T13:41:27+08:00")

    assert value == datetime(2026, 6, 3, 5, 41, 27)
    assert value.tzinfo is None
