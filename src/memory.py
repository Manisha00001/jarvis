"""Local, persistent memory and voice reminders for Jarvis.

Everything lives in a local SQLite database (Python's built-in ``sqlite3``)
under the project's ``data/`` directory. Nothing is ever sent to an external
service. Reminders are delivered by a lightweight asyncio scheduler that runs
only while the agent is running.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

logger = logging.getLogger("jarvis.memory")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
_DB_FILENAME = "jarvis.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    due_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    delivered_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_reminders_pending_due
    ON reminders (status, due_at);
"""


class StoreError(Exception):
    """A user-facing local storage failure."""


class AmbiguousTimeError(ValueError):
    """A reminder time that cannot be resolved without guessing."""


def default_db_path() -> Path:
    """Return the local SQLite path, overridable with ``JARVIS_DATA_DIR``."""
    override = os.environ.get("JARVIS_DATA_DIR")
    data_dir = Path(override).expanduser() if override else _DEFAULT_DATA_DIR
    return data_dir / _DB_FILENAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    """Serialize a moment as UTC ISO-8601 at second resolution."""
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def format_local(iso_value: str) -> str:
    """Render a stored UTC timestamp in the machine's local time."""
    try:
        moment = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime("%A %d %B %Y at %I:%M %p")


_TIME_FORMATS = ("%H:%M", "%H", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p")


def parse_time(value: str) -> time:
    """Parse a clock time given as 24-hour (``19:00``) or 12-hour (``7 PM``)."""
    text = value.strip().lower().replace(".", "")
    text = " ".join(text.split())
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(
        "I did not understand that time. Please give a time such as 7 PM or 19:00."
    )


def parse_day(value: str | None, now: datetime) -> date:
    """Resolve a day given as ``today``, ``tomorrow``, or ``YYYY-MM-DD``."""
    if value is None:
        return now.date()
    text = value.strip().lower()
    if not text or text == "today":
        return now.date()
    if text == "tomorrow":
        return now.date() + timedelta(days=1)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            "I did not understand that date. Please give a day such as today, "
            "tomorrow, or a calendar date like 2026-10-20."
        ) from exc


def resolve_due_at(
    day: str | None, clock: str, *, now: datetime | None = None
) -> datetime:
    """Return the absolute UTC time for a local day and clock time.

    ``now`` defaults to the current local time and exists for testing. Raises
    :class:`AmbiguousTimeError` when the requested time has already passed,
    rather than guessing today versus tomorrow.
    """
    local_now = now or datetime.now()
    clock_time = parse_time(clock)
    target_day = parse_day(day, local_now)
    naive_local = datetime.combine(target_day, clock_time)
    if naive_local <= local_now:
        raise AmbiguousTimeError(
            "That time has already passed today. Should I set it for tomorrow, "
            "or did you mean a different day?"
        )
    return naive_local.astimezone(timezone.utc)


class MemoryStore:
    """A small SQLite-backed store for memories and reminders."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise StoreError(
                f"Could not prepare the local Jarvis database: {exc}"
            ) from exc

    def _query(self, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        try:
            with self._connect() as connection:
                return connection.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StoreError(
                f"Could not read the local Jarvis database: {exc}"
            ) from exc

    # -- Memories ---------------------------------------------------------

    def save_memory(self, content: str, category: str = "general") -> dict[str, object]:
        text = content.strip()
        if not text:
            raise StoreError("There is nothing for me to remember yet.")
        label = (category or "general").strip().lower() or "general"
        created_at = _iso(_utc_now())
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO memories (content, category, created_at) "
                    "VALUES (?, ?, ?)",
                    (text, label, created_at),
                )
                memory_id = cursor.lastrowid
        except sqlite3.Error as exc:
            raise StoreError(f"I could not save that to memory: {exc}") from exc
        return {
            "id": memory_id,
            "content": text,
            "category": label,
            "created_at": created_at,
        }

    def search_memories(self, query: str, limit: int = 20) -> list[dict[str, object]]:
        text = query.strip()
        if not text:
            raise StoreError("I need a word or phrase to search your memories.")
        pattern = f"%{text}%"
        rows = self._query(
            "SELECT id, content, category, created_at FROM memories "
            "WHERE content LIKE ? OR category LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (pattern, pattern, limit),
        )
        return [dict(row) for row in rows]

    def list_memories(self, limit: int = 20) -> list[dict[str, object]]:
        rows = self._query(
            "SELECT id, content, category, created_at FROM memories "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    def delete_memory(self, memory_id: int) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "DELETE FROM memories WHERE id = ?", (memory_id,)
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StoreError(f"I could not delete that memory: {exc}") from exc

    # -- Reminders --------------------------------------------------------

    def create_reminder(self, message: str, due_at: datetime) -> dict[str, object]:
        text = message.strip()
        if not text:
            raise StoreError("I need to know what to remind you about.")
        created_at = _iso(_utc_now())
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO reminders (message, due_at, created_at, status) "
                    "VALUES (?, ?, ?, 'pending')",
                    (text, _iso(due_at), created_at),
                )
                reminder_id = cursor.lastrowid
        except sqlite3.Error as exc:
            raise StoreError(f"I could not save that reminder: {exc}") from exc
        return {
            "id": reminder_id,
            "message": text,
            "due_at": _iso(due_at),
            "created_at": created_at,
        }

    def list_reminders(self) -> list[dict[str, object]]:
        rows = self._query(
            "SELECT id, message, due_at FROM reminders "
            "WHERE status = 'pending' ORDER BY due_at ASC",
            (),
        )
        return [dict(row) for row in rows]

    def cancel_reminder(self, reminder_id: int) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE reminders SET status = 'cancelled' "
                    "WHERE id = ? AND status = 'pending'",
                    (reminder_id,),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StoreError(f"I could not cancel that reminder: {exc}") from exc

    def due_reminders(self, now: datetime | None = None) -> list[dict[str, object]]:
        moment = _iso(now or _utc_now())
        rows = self._query(
            "SELECT id, message, due_at FROM reminders "
            "WHERE status = 'pending' AND due_at <= ? ORDER BY due_at ASC",
            (moment,),
        )
        return [dict(row) for row in rows]

    def claim_reminder(self, reminder_id: int) -> bool:
        """Atomically mark a pending reminder delivered.

        Returns ``True`` only for the caller that wins the claim, so a reminder
        can never be delivered more than once.
        """
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE reminders SET status = 'delivered', delivered_at = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (_iso(_utc_now()), reminder_id),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StoreError(f"I could not update that reminder: {exc}") from exc


class ReminderScheduler:
    """Deliver due reminders while the agent session is running."""

    def __init__(
        self,
        store: MemoryStore,
        announce: Callable[[str, str], Awaitable[None]],
        *,
        poll_interval: float = 5.0,
    ) -> None:
        self._store = store
        self._announce = announce
        self._poll_interval = poll_interval
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(
                self._run(), name="jarvis-reminder-scheduler"
            )

    def wake(self) -> None:
        """Ask the scheduler to check for due reminders right away."""
        self._wake.set()

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._deliver_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Reminder scheduler tick failed.")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            self._wake.clear()

    async def _deliver_due(self) -> None:
        for reminder in self._store.due_reminders():
            reminder_id = int(reminder["id"])  # type: ignore[arg-type]
            if not self._store.claim_reminder(reminder_id):
                # Another tick (or a previous run) already handled it.
                continue
            try:
                await self._announce(str(reminder["message"]), str(reminder["due_at"]))
            except Exception:
                logger.exception("Could not announce reminder %s.", reminder_id)


class MemoryTools:
    """Tool-calling surface for Jarvis's persistent memory."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    @property
    def tools(self) -> list:
        return [
            self.save_memory,
            self.search_memories,
            self.list_memories,
            self.delete_memory,
        ]

    @function_tool()
    async def save_memory(
        self, context: RunContext, content: str, category: str = "general"
    ) -> dict[str, object]:
        """Save a fact to Jarvis's local, persistent memory.

        Call this only when the user explicitly asks you to remember something,
        and save exactly what they asked you to remember. Never save personal
        details on your own initiative. If the request is vague or missing the
        actual detail to store, ask a short clarifying question instead of
        calling this tool.

        Args:
            content: The exact fact or detail the user asked you to remember.
            category: A short label such as personal, work, or preference.
        """
        try:
            memory = self._store.save_memory(content, category)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        return {"status": "saved", **memory}

    @function_tool()
    async def search_memories(
        self, context: RunContext, query: str
    ) -> dict[str, object]:
        """Search saved memories by keyword to recall something for the user.

        Args:
            query: A word or phrase to look for in the saved memories.
        """
        try:
            memories = self._store.search_memories(query)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        return {"status": "ok", "count": len(memories), "memories": memories}

    @function_tool()
    async def list_memories(
        self, context: RunContext, limit: int = 20
    ) -> dict[str, object]:
        """List recently saved memories, newest first.

        Use this when the user asks what you remember about them.

        Args:
            limit: The maximum number of memories to return.
        """
        try:
            memories = self._store.list_memories(limit)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        return {"status": "ok", "count": len(memories), "memories": memories}

    @function_tool()
    async def delete_memory(
        self, context: RunContext, memory_id: int
    ) -> dict[str, object]:
        """Delete one saved memory by its id.

        Search or list memories first to find the right id. If it is unclear
        which memory the user means, ask them before deleting.

        Args:
            memory_id: The id of the memory to delete.
        """
        try:
            deleted = self._store.delete_memory(memory_id)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        if not deleted:
            return {"status": "not_found", "id": memory_id}
        return {"status": "deleted", "id": memory_id}


class ReminderTools:
    """Tool-calling surface for Jarvis's voice reminders."""

    def __init__(self, store: MemoryStore, scheduler: ReminderScheduler) -> None:
        self._store = store
        self._scheduler = scheduler

    @property
    def tools(self) -> list:
        return [
            self.get_current_datetime,
            self.create_reminder,
            self.list_reminders,
            self.cancel_reminder,
        ]

    @function_tool()
    async def get_current_datetime(self, context: RunContext) -> dict[str, str]:
        """Get the current local date, weekday, and time.

        Call this before resolving relative days such as next Monday so you can
        work out the correct calendar date.
        """
        now = datetime.now()
        return {
            "date": now.date().isoformat(),
            "weekday": now.strftime("%A"),
            "time": now.strftime("%H:%M"),
        }

    @function_tool()
    async def create_reminder(
        self,
        context: RunContext,
        message: str,
        time: str,
        date: str | None = None,
    ) -> dict[str, object]:
        """Schedule a reminder Jarvis will speak aloud when it becomes due.

        Use this whenever the user asks to be reminded about something. If the
        user did not give a time, ask them for one. Give the time in 24-hour
        form. If the time is ambiguous, or a time-only request has already
        passed today, ask the user to clarify instead of guessing.

        Args:
            message: What to remind the user about, in a short phrase.
            time: The time of day in 24-hour form, such as 19:00 or 09:00.
            date: today, tomorrow, or a calendar date like 2026-10-20. Defaults
                to today.
        """
        try:
            due_at = resolve_due_at(date, time)
        except AmbiguousTimeError as exc:
            raise ToolError(str(exc)) from exc
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        try:
            reminder = self._store.create_reminder(message, due_at)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc

        self._scheduler.wake()
        return {
            "status": "scheduled",
            "id": reminder["id"],
            "message": reminder["message"],
            "due_at": format_local(str(reminder["due_at"])),
        }

    @function_tool()
    async def list_reminders(self, context: RunContext) -> dict[str, object]:
        """List the reminders that are still pending, soonest first."""
        try:
            reminders = self._store.list_reminders()
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        return {
            "status": "ok",
            "count": len(reminders),
            "reminders": [
                {
                    "id": reminder["id"],
                    "message": reminder["message"],
                    "due_at": format_local(str(reminder["due_at"])),
                }
                for reminder in reminders
            ],
        }

    @function_tool()
    async def cancel_reminder(
        self, context: RunContext, reminder_id: int
    ) -> dict[str, object]:
        """Cancel one pending reminder by its id.

        List reminders first to find the right id, and confirm with the user if
        it is unclear which reminder they mean.

        Args:
            reminder_id: The id of the reminder to cancel.
        """
        try:
            cancelled = self._store.cancel_reminder(reminder_id)
        except StoreError as exc:
            raise ToolError(str(exc)) from exc
        if not cancelled:
            return {"status": "not_found", "id": reminder_id}
        return {"status": "cancelled", "id": reminder_id}
