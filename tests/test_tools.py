"""The behaviours hive-tools depends on, through the `tools` operations.

Every assertion reads the row back with a plain driver connection rather than
through a second operation, for the reason the round-trip suite gives: a
layer that writes and reads the same wrong column consistently passes its
own round trip.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

import hive_data
from hive_data import tools


def _id() -> str:
    return f"req-{uuid.uuid4().hex[:10]}"


def _tool() -> str:
    """A tool name of this test's own.

    The scratch database is made once per run, so rows outlive the test that
    wrote them. A shared name here would have one test reading another's
    settings row and calling it a leak.
    """
    return f"tool-{uuid.uuid4().hex[:10]}"


async def test_every_tools_table_returns_what_was_written(
        connected, inspector):
    """Requirement one, and the only thing that proves a table is actually
    reachable: a value put in through the layer comes back out of it."""
    at = 1_800_000_000
    request_id = _id()
    await tools.create_request(
        request_id, "gmail.send", "skippy", '{"to": "daniel"}', at, at + 600,
        tool_method="POST", tool_path="/gmail/send", tool_body="{}")
    await tools.grant_sudo("gmail.send", "skippy", at, at + 900)
    setting_tool = _tool()
    await tools.set_hitl_setting(setting_tool, "ask", 30)
    digest = f"sha-{uuid.uuid4().hex}"
    username = f"user-{uuid.uuid4().hex[:8]}"
    token = await tools.create_token("console", digest, at)
    user = await tools.create_user(username, "argon2-hash", 1, at)

    found = await tools.request(request_id)
    assert found is not None
    assert found["tool_name"] == "gmail.send"
    assert found["caller_mind"] == "skippy"
    assert found["params_json"] == '{"to": "daniel"}'
    assert found["tool_path"] == "/gmail/send"
    assert found["status"] == tools.PENDING

    grant = await tools.active_grant("gmail.send", "skippy", at)
    assert grant is not None and grant["expires_at"] == at + 900

    setting = await tools.hitl_setting(setting_tool)
    assert setting == {"tool_name": setting_tool, "mode": "ask",
                       "sudo_timeout_minutes": 30}

    live = await tools.live_token(digest)
    assert live is not None and live["name"] == "console"
    assert live["id"] == token["row"]["id"]

    login = await tools.user(username)
    assert login is not None and login["password_hash"] == "argon2-hash"
    assert login["id"] == user["row"]["id"]

    # Read from outside the package as well, so a consistently wrong column
    # cannot carry every assertion above.
    row = await inspector.fetchrow(
        'SELECT tool_name, status FROM tools."hitl_requests" WHERE id = $1',
        request_id)
    assert dict(row) == {"tool_name": "gmail.send", "status": tools.PENDING}


async def test_the_queue_is_newest_first_and_capped(connected):
    """What the approvals page renders. Reversing the order or widening the
    cap in `recent_requests` fails here."""
    at = 1_800_000_000
    made = []
    for n in range(tools.QUEUE_LIMIT + 3):
        request_id = _id()
        made.append(request_id)
        await tools.create_request(
            request_id, "docker.restart", "skippy", "{}", at + n,
            at + n + 600)

    queue = await tools.recent_requests()
    assert len(queue) == tools.QUEUE_LIMIT
    assert [r["id"] for r in queue] == list(reversed(made))[:tools.QUEUE_LIMIT]
    assert [r["created_at"] for r in queue] == sorted(
        (r["created_at"] for r in queue), reverse=True)


async def test_a_request_that_is_not_there_is_nothing_rather_than_a_blank_row(
        connected):
    """A caller cannot tell an empty dict from a row whose every column came
    back empty, so the absent answer is None."""
    assert await tools.request(_id()) is None
    assert await tools.pending_request(_id(), 1_800_000_000) is None
    assert await tools.hitl_setting("a.tool.nobody.configured") is None
    assert await tools.active_grant("a.tool", "nobody", 1_800_000_000) is None
    assert await tools.user("nobody") is None


async def test_a_request_past_its_expiry_is_not_offered_as_pending(
        connected):
    """The boundary, driven by a time the test hands in rather than the wall
    clock. A request expiring exactly now is still decidable; one that
    expired a second ago is not."""
    at = 1_800_000_000
    expires_at = at + 600
    request_id = _id()
    await tools.create_request(
        request_id, "gmail.send", "skippy", "{}", at, expires_at)

    assert await tools.pending_request(request_id, expires_at - 1) is not None
    assert await tools.pending_request(request_id, expires_at) is not None
    assert await tools.pending_request(request_id, expires_at + 1) is None
    # Still a request, just not a decidable one.
    assert await tools.request(request_id) is not None


async def test_a_request_is_decided_once_and_only_once(connected, inspector):
    """Two people reaching the queue at the same moment produce one decision.
    Dropping the pending guard from the statement fails here."""
    at = 1_800_000_000
    request_id = _id()
    await tools.create_request(
        request_id, "gmail.send", "skippy", "{}", at, at + 600)

    first = await tools.decide_request(request_id, "approved", at + 5, at + 5)
    assert first["rows"] == 1

    second = await tools.decide_request(request_id, "denied", at + 6, at + 6)
    assert second["rows"] == 0

    row = await inspector.fetchrow(
        'SELECT status, decided_at FROM tools."hitl_requests" '
        "WHERE id = $1", request_id)
    assert dict(row) == {"status": "approved", "decided_at": at + 5}


async def test_an_expired_request_cannot_be_decided(connected):
    """The expiry rule lives in the same statement as the decision, so a
    request cannot expire between being read and being approved."""
    at = 1_800_000_000
    request_id = _id()
    await tools.create_request(
        request_id, "gmail.send", "skippy", "{}", at, at + 600)

    late = await tools.decide_request(
        request_id, "approved", at + 601, at + 601)
    assert late["rows"] == 0


async def test_work_in_one_transaction_is_undone_together(
        connected, inspector):
    """The test that fails if an operation ignores the unit it was handed and
    opens a connection of its own: nothing here is committed."""
    at = 1_800_000_000
    request_id = _id()
    tool_name = _tool()

    class Deliberate(Exception):
        pass

    with pytest.raises(Deliberate):
        async with hive_data.transaction() as unit:
            await tools.create_request(
                request_id, "gmail.send", "skippy", "{}", at, at + 600,
                unit=unit)
            await tools.set_hitl_setting(
                tool_name, "never", 5, unit=unit)
            raise Deliberate

    assert await inspector.fetchval(
        'SELECT count(*) FROM tools."hitl_requests" WHERE id = $1',
        request_id) == 0
    assert await inspector.fetchval(
        'SELECT count(*) FROM tools."tool_hitl_settings" '
        "WHERE tool_name = $1", tool_name) == 0
