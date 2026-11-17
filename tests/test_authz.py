"""Authorization regressions: only a superadmin may add or remove admins."""
import asyncio

import pytest

import database as db
from handlers import admin_settings


class _FakeCallback:
    def __init__(self, data: str, user_id: int = 555):
        self.data = data
        self.from_user = type("U", (), {"id": user_id})()
        self.message = object()
        self.answers: list[tuple] = []

    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))


class _FakeState:
    def __init__(self):
        self.state = None
        self.cleared = False

    async def set_state(self, value):
        self.state = value

    async def clear(self):
        self.cleared = True

    async def get_data(self):
        return {"new_admin_tg_id": 777}

    async def update_data(self, **kwargs):
        pass


@pytest.fixture
def plain_admin(monkeypatch):
    """The caller is a regular admin, not a superadmin; record any admin-table writes."""
    writes: list[str] = []

    async def is_superadmin(_tg_id):
        return False

    async def add_admin(**kwargs):
        writes.append("add")

    async def remove_admin(_tg_id):
        writes.append("remove")
        return True

    monkeypatch.setattr(db, "is_superadmin", is_superadmin)
    monkeypatch.setattr(db, "add_admin", add_admin)
    monkeypatch.setattr(db, "remove_admin", remove_admin)
    return writes


def test_regular_admin_cannot_start_adding_admin(plain_admin):
    cb, state = _FakeCallback("add_admin_start"), _FakeState()
    asyncio.run(admin_settings.cb_add_admin_start(cb, state))
    assert state.state is None
    assert cb.answers and cb.answers[0][1].get("show_alert") is True


def test_regular_admin_cannot_remove_admin(plain_admin):
    cb = _FakeCallback("del_admin_777")
    asyncio.run(admin_settings.cb_del_admin(cb))
    assert plain_admin == []


def test_regular_admin_cannot_finish_adding_admin(plain_admin):
    msg = type("M", (), {"from_user": type("U", (), {"id": 555})(), "text": "Yangi Admin"})()
    state = _FakeState()
    asyncio.run(admin_settings.process_new_admin_name(msg, state))
    assert plain_admin == []
    assert state.cleared is True
