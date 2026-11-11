"""The named operations over the `staff` schema: the chief of staff's ledger.

The ledger holds only what Daniel has handed the chief of staff to watch. A
task is a name, a short description (the task itself, or a line naming the
board item it covers) and a status; the sessions working it are pairs in
`staff.task_sessions`. The chief of staff and its tick both reach the ledger
through these operations rather than writing SQL.

A status is a row of `staff.statuses`, not a string this module checks. A
status that is not there is refused by the foreign key as
`MissingReference`, inside the same statement that would have written it,
so a refused update leaves the task exactly as it was.

The session in a pair is `core.sessions.id`, the hive-comms session id that
survives every rotation, never a harness conversation id. A session works
one task at a time: attaching a session that is already paired is a
`Conflict`, to this task or another.

Every operation takes an optional `unit` and behaves as the `core` ones do:
given one it runs inside that caller's transaction, given none it runs on
its own connection and commits by itself.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from . import _sql
from .core import _execute, _execute_returning, _fetch, _fetch_one
from .errors import ValueRefused
from .rows import UNSET
from .schema import COLUMNS, qualified, select_list
from .unit import Unit

Row = dict[str, Any]

STATUSES = "staff.statuses"
TASKS = "staff.tasks"
TASK_SESSIONS = "staff.task_sessions"

#: What `update_task` may set. `updated_at` is moved by the operation
#: itself, and `id` and `created_at` never move.
_SETTABLE = frozenset({"name", "description", "status", "updated_at"})


def _now(now: float | None) -> float:
    return time.time() if now is None else now


# ----------------------------------------------------------------- statuses

async def statuses(*, unit: Unit | None = None) -> list[str]:
    """Every status a task may be given, by name."""
    rows = await _fetch(
        unit, f'SELECT "name" FROM {qualified(STATUSES)} ORDER BY "name"')
    return [r["name"] for r in rows]


# -------------------------------------------------------------------- tasks

async def create_task(name: str, status: str, *, description: str = "",
                      task_id: str | None = None, now: float | None = None,
                      unit: Unit | None = None) -> Row:
    """Open a task and return it as stored.

    `task_id` defaults to a fresh uuid; `now` stamps both `created_at` and
    `updated_at` and defaults to the wall clock. A status not in
    `staff.statuses` is refused as `MissingReference` and nothing is written.
    """
    moment = _now(now)
    sql, args = _sql.insert(TASKS, {
        "id": task_id if task_id is not None else uuid.uuid4().hex,
        "name": name, "description": description, "status": status,
        "created_at": moment, "updated_at": moment,
    }, returning=COLUMNS[TASKS])
    return (await _execute_returning(unit, sql, *args)).get("row")


async def task(task_id: str, *, unit: Unit | None = None) -> Row | None:
    """One task by id, or None when there is no such task."""
    return await _fetch_one(
        unit, f"SELECT {select_list(TASKS)} FROM {qualified(TASKS)} "
        'WHERE "id" = $1', task_id)


async def tasks(*, status: str | None = None,
                unit: Unit | None = None) -> list[Row]:
    """Every task, or every task in one status; most recently moved first."""
    where, args = ("", []) if status is None else ('WHERE "status" = $1',
                                                   [status])
    return await _fetch(
        unit, f"SELECT {select_list(TASKS)} FROM {qualified(TASKS)} {where} "
        'ORDER BY "updated_at" DESC, "id"', *args)


async def update_task(task_id: str, *, name: Any = UNSET,
                      description: Any = UNSET, status: Any = UNSET,
                      now: float | None = None,
                      unit: Unit | None = None) -> Row | None:
    """Change a task's name, description or status; `updated_at` moves.

    Only what is passed is written. Returns the task as it now stands, or
    None when there is no such task. A status not in `staff.statuses` is
    refused as `MissingReference` and the task is left unchanged.
    """
    values = _sql.passed(
        {"name": name, "description": description, "status": status})
    if not values:
        raise ValueRefused(
            "an update of a staff task named nothing to change. Moving "
            "updated_at alone would report the task as touched when nothing "
            "about it was.")
    values["updated_at"] = _now(now)
    sql, args = _sql.update(TASKS, values, {"id": task_id},
                            settable=_SETTABLE, returning=COLUMNS[TASKS])
    return (await _execute_returning(unit, sql, *args)).get("row")


# ----------------------------------------------------------------- sessions

async def attach_session(task_id: str, session_id: str, *,
                         now: float | None = None,
                         unit: Unit | None = None) -> Row:
    """Pair a hive-comms session with a task. Reports rows changed.

    `MissingReference` when the task or the session is not there; `Conflict`
    when the session is already paired, with this task or another.
    """
    sql, args = _sql.insert(TASK_SESSIONS, {
        "session_id": session_id, "task_id": task_id,
        "attached_at": _now(now),
    })
    return await _execute(unit, sql, *args)


async def detach_session(task_id: str, session_id: str, *,
                         unit: Unit | None = None) -> Row:
    """Unpair a session from a task. Reports rows changed; 0 if unpaired."""
    clause, args = _sql.where(
        TASK_SESSIONS, {"task_id": task_id, "session_id": session_id})
    return await _execute(
        unit, f"DELETE FROM {qualified(TASK_SESSIONS)} WHERE {clause}", *args)


async def task_sessions(task_id: str, *,
                        unit: Unit | None = None) -> list[Row]:
    """The sessions paired with a task, in the order they were attached."""
    return await _fetch(
        unit, f"SELECT {select_list(TASK_SESSIONS)} "
        f'FROM {qualified(TASK_SESSIONS)} WHERE "task_id" = $1 '
        'ORDER BY "attached_at", "session_id"', task_id)


async def task_for_session(session_id: str, *,
                           unit: Unit | None = None) -> Row | None:
    """The task a session is working, or None when it is paired with none."""
    columns = ", ".join(f't."{c}"' for c in COLUMNS[TASKS])
    return await _fetch_one(
        unit, f"SELECT {columns} FROM {qualified(TASKS)} AS t "
        f'JOIN {qualified(TASK_SESSIONS)} AS p ON p."task_id" = t."id" '
        'WHERE p."session_id" = $1', session_id)
