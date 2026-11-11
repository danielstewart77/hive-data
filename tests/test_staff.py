"""The chief of staff's ledger, through the `staff` operations.

What a write produced is read back with a plain driver connection as well as
through the layer, for the reason the round-trip suite gives: a layer that
writes and reads the same wrong column consistently passes its own round
trip.
"""

from __future__ import annotations

import uuid

import pytest

import hive_data
from hive_data import staff


async def _session(mind_id: str, clock: float) -> str:
    session_id = f"sess-{uuid.uuid4().hex[:10]}"
    await hive_data.core.create_session(
        id=session_id, surface="telegram", surface_id="chat-1",
        mind_id=mind_id, created_at=clock, last_active=clock)
    return session_id


async def test_a_created_task_comes_back_with_its_name_description_and_status(
        connected, inspector, clock):
    made = await staff.create_task(
        "Move coach into the health app", "in progress",
        description="implementing a new feature for the health app, "
                    "feature 6.2", now=clock)

    found = await staff.task(made["id"])
    assert found is not None
    assert found["name"] == "Move coach into the health app"
    assert found["description"] == ("implementing a new feature for the "
                                    "health app, feature 6.2")
    assert found["status"] == "in progress"
    stored = await inspector.fetchrow(
        "SELECT name, description, status FROM staff.tasks WHERE id = $1",
        made["id"])
    assert dict(stored) == {
        "name": "Move coach into the health app",
        "description": "implementing a new feature for the health app, "
                       "feature 6.2",
        "status": "in progress"}


async def test_two_sessions_on_one_task_are_both_listed_and_each_finds_it(
        connected, a_mind, clock):
    made = await staff.create_task("Bake-off", "in progress", now=clock)
    first = await _session(a_mind, clock)
    second = await _session(a_mind, clock)
    await staff.attach_session(made["id"], first, now=clock)
    await staff.attach_session(made["id"], second, now=clock + 1)

    listed = await staff.task_sessions(made["id"])
    assert [r["session_id"] for r in listed] == [first, second]
    assert (await staff.task_for_session(first))["id"] == made["id"]
    assert (await staff.task_for_session(second))["id"] == made["id"]


async def test_a_status_not_in_the_lookup_is_refused_and_the_task_is_unchanged(
        connected, inspector, clock):
    made = await staff.create_task("Watch this", "on hold", now=clock)

    with pytest.raises(hive_data.MissingReference):
        await staff.update_task(made["id"], status="abandoned",
                                name="renamed", now=clock + 60)

    stored = await inspector.fetchrow(
        "SELECT name, status, updated_at FROM staff.tasks WHERE id = $1",
        made["id"])
    assert dict(stored) == {"name": "Watch this", "status": "on hold",
                            "updated_at": clock}
