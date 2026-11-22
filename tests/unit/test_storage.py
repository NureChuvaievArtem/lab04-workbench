"""Unit-тести журналу SQLite (workbench/storage.py)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from workbench.storage import HistoryStore


def test_history_store_crud_and_summary(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "wb.db")
    r1 = store.add("ask", "Q1", "A1", 1, 100, 1.2)
    r2 = store.add("team", "SL-142", "PR", 4, 4000, 5.4, stop_reason="approved")
    store.rate(r1, 1)
    store.rate(r2, 0)
    store.mark_saved(r2, "/tmp/Inbox/SL-142.md")

    summary = store.summary()
    assert summary["runs"] == 2
    assert summary["tokens"] == 4100
    assert summary["positive_share"] == pytest.approx(0.5)
    assert summary["saved"] == 1
    assert len(store.list()) == 2


def test_history_store_enforces_check_constraints(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "wb.db")
    with pytest.raises(sqlite3.IntegrityError):
        store.add("invalid_kind", "x", "y", 1, 10, 0.1)
    rid = store.add("ask", "Q", "A", 1, 10, 0.1)
    with pytest.raises(sqlite3.IntegrityError):
        store.rate(rid, 5)
