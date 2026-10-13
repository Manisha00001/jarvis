"""Tests for local memory storage and voice reminders."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from livekit.agents.llm import ToolError

from memory import (
    AmbiguousTimeError,
    MemoryStore,
    MemoryTools,
    ReminderScheduler,
    ReminderTools,
    StoreError,
    parse_time,
    resolve_due_at,
)


@pytest.fixture()
def store(tmp_path) -> MemoryStore:
    return MemoryStore(tmp_path / "jarvis-test.db")


async def _noop_announce(message: str, due_at: str) -> None:
    return None


# -- Memory -----------------------------------------------------------------


def test_memory_crud(store: MemoryStore) -> None:
    saved = store.save_memory("Likes Earl Grey tea", "preference")
    assert saved["id"] == 1
    assert saved["category"] == "preference"

    results = store.search_memories("tea")
    assert [row["content"] for row in results] == ["Likes Earl Grey tea"]

    assert len(store.list_memories()) == 1

    assert store.delete_memory(1) is True
    assert store.list_memories() == []
    assert store.delete_memory(999) is False


def test_memory_survives_reopen(store: MemoryStore) -> None:
    store.save_memory("Remember the milk")

    reopened = MemoryStore(store.db_path)
    assert [row["content"] for row in reopened.list_memories()] == ["Remember the milk"]


def test_memory_requires_content(store: MemoryStore) -> None:
    with pytest.raises(StoreError):
        store.save_memory("   ")


# -- Reminders --------------------------------------------------------------


def test_reminder_create_list_cancel(store: MemoryStore) -> None:
    due = datetime.now(timezone.utc) + timedelta(hours=1)
    created = store.create_reminder("Study Java", due)

    listed = store.list_reminders()
    assert [row["id"] for row in listed] == [created["id"]]
    assert listed[0]["message"] == "Study Java"

    assert store.cancel_reminder(created["id"]) is True
    assert store.list_reminders() == []
    assert store.cancel_reminder(created["id"]) is False


def test_due_reminder_and_claim_prevents_duplicates(store: MemoryStore) -> None:
    due = datetime.now(timezone.utc) - timedelta(seconds=1)
    created = store.create_reminder("Stand up", due)

    assert [row["id"] for row in store.due_reminders()] == [created["id"]]

    assert store.claim_reminder(created["id"]) is True
    assert store.claim_reminder(created["id"]) is False
    assert store.due_reminders() == []


async def test_scheduler_delivers_due_reminder_once(store: MemoryStore) -> None:
    announced: list[tuple[str, str]] = []

    async def announce(message: str, due_at: str) -> None:
        announced.append((message, due_at))

    due = datetime.now(timezone.utc) - timedelta(seconds=1)
    store.create_reminder("Take a break", due)

    scheduler = ReminderScheduler(store, announce, poll_interval=0.05)
    scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    assert len(announced) == 1
    assert announced[0][0] == "Take a break"
    assert store.due_reminders() == []
    assert store.list_reminders() == []


async def test_scheduler_wakes_for_new_reminder(store: MemoryStore) -> None:
    announced: list[str] = []

    async def announce(message: str, due_at: str) -> None:
        announced.append(message)

    scheduler = ReminderScheduler(store, announce, poll_interval=5)
    scheduler.start()

    due = datetime.now(timezone.utc) - timedelta(seconds=1)
    store.create_reminder("Pick up the keys", due)
    scheduler.wake()

    for _ in range(40):
        if announced:
            break
        await asyncio.sleep(0.05)
    await scheduler.stop()

    assert announced == ["Pick up the keys"]


# -- Time resolution --------------------------------------------------------


def test_parse_time_variants() -> None:
    assert parse_time("19:00").hour == 19
    assert parse_time("7 PM").hour == 19
    assert parse_time("7pm").hour == 19
    assert parse_time("9 am").hour == 9


def test_resolve_due_at_tomorrow_morning() -> None:
    now = datetime(2026, 10, 12, 15, 0, 0)
    due = resolve_due_at("tomorrow", "09:00", now=now)
    local = due.astimezone().replace(tzinfo=None)
    assert local == datetime(2026, 10, 13, 9, 0, 0)


def test_resolve_due_at_rejects_past_time() -> None:
    now = datetime(2026, 10, 12, 21, 0, 0)
    with pytest.raises(AmbiguousTimeError):
        resolve_due_at(None, "19:00", now=now)


# -- Tool surface -----------------------------------------------------------


async def test_memory_tools_round_trip(store: MemoryStore) -> None:
    tools = MemoryTools(store)

    saved = await tools.save_memory(None, content="Birthday is 1 January")
    assert saved["status"] == "saved"

    found = await tools.search_memories(None, query="Birthday")
    assert found["count"] == 1

    deleted = await tools.delete_memory(None, memory_id=saved["id"])
    assert deleted["status"] == "deleted"

    missing = await tools.delete_memory(None, memory_id=12345)
    assert missing["status"] == "not_found"


async def test_memory_tool_rejects_empty(store: MemoryStore) -> None:
    tools = MemoryTools(store)
    with pytest.raises(ToolError):
        await tools.save_memory(None, content="   ")


async def test_reminder_tools_create_list_cancel(store: MemoryStore) -> None:
    scheduler = ReminderScheduler(store, _noop_announce)
    tools = ReminderTools(store, scheduler)

    created = await tools.create_reminder(
        None, message="Study Java", time="09:00", date="tomorrow"
    )
    assert created["status"] == "scheduled"

    listed = await tools.list_reminders(None)
    assert listed["count"] == 1

    cancelled = await tools.cancel_reminder(None, reminder_id=created["id"])
    assert cancelled["status"] == "cancelled"


async def test_reminder_tool_rejects_bad_time(store: MemoryStore) -> None:
    scheduler = ReminderScheduler(store, _noop_announce)
    tools = ReminderTools(store, scheduler)
    with pytest.raises(ToolError):
        await tools.create_reminder(None, message="Vague", time="not-a-time")


# -- Existing project integrity ---------------------------------------------


def test_existing_modules_import() -> None:
    from browser import BrowserManager
    from tools import BrowserTools

    assert BrowserManager is not None
    assert BrowserTools is not None


def test_agent_registers_memory_and_reminder_tools(store: MemoryStore) -> None:
    import agent

    scheduler = ReminderScheduler(store, _noop_announce)
    assistant = agent.Assistant(memory_store=store, reminder_scheduler=scheduler)

    memory_ids = {tool.id for tool in assistant.memory_tools.tools}
    reminder_ids = {tool.id for tool in assistant.reminder_tools.tools}

    assert memory_ids == {
        "save_memory",
        "search_memories",
        "list_memories",
        "delete_memory",
    }
    assert reminder_ids == {
        "get_current_datetime",
        "create_reminder",
        "list_reminders",
        "cancel_reminder",
    }
    assert agent.reminder_instructions("x", "2026-10-12T12:00:00+00:00")
