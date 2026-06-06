from __future__ import annotations

from app.routers import reports


def test_report_datetime_helper_accepts_iso_string():
    value = reports._to_report_iso("2026-06-06T10:37:24.033483")

    assert value.startswith("2026-06-06T")


def test_report_datetime_helper_keeps_unparseable_string():
    assert reports._to_report_iso("not-a-date") == "not-a-date"


def test_report_list_dedupes_dual_written_reports():
    documents = [
        {"_id": "generic", "analysis_id": "600519_20260606_103724"},
        {"_id": "analysis_reports:600519_20260606_103724", "analysis_id": "600519_20260606_103724"},
        {"_id": "other", "analysis_id": "000001_20260606_103724"},
    ]

    deduped = reports._dedupe_report_documents(documents)

    assert [doc["_id"] for doc in deduped] == ["generic", "other"]
