"""White-label checks: every module imports, and the Excel report is titled with RESTAURANT_NAME."""
import asyncio
import importlib

import openpyxl
import pytest


def test_all_modules_import():
    # bot.py imports every router, the scheduler and the DB layer
    module = importlib.import_module("bot")
    assert module.logger.name == "smena_bot"


class _FakeConn:
    async def fetch(self, *args, **kwargs):
        return []


class _FakeAcquire:
    async def __aenter__(self):
        return _FakeConn()

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquire()


@pytest.mark.parametrize("name", ["Smena", "Grill House"])
def test_excel_report_title_uses_restaurant_name(monkeypatch, name):
    import database as db
    from utils import excel_generator

    async def no_workers(year, month):
        return []

    monkeypatch.setattr(excel_generator, "RESTAURANT_NAME", name)
    monkeypatch.setattr(db, "get_report_workers_for_month", no_workers)
    monkeypatch.setattr(db, "pool", _FakePool(), raising=False)

    stream = asyncio.run(excel_generator.generate_monthly_report_excel(2026, 3))
    wb = openpyxl.load_workbook(stream)
    title = wb.worksheets[0]["A1"].value
    assert title.startswith(f"{name.upper()} — Mart 2026")
