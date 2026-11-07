"""The graph, the soul, the registry and the holders, through the layer.

Every assertion on what a write produced is read with the `inspector` — a
plain driver connection outside the package — because a round trip through
one module passes even when the write and the read agree on the same wrong
column.

The concurrency tests here are the reason this story exists. Lucent's upsert
is find-then-insert and its properties merge is a Python read-modify-write;
SQLite's single writer hid both, and a pool does not.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

import hive_data
from hive_data import graph

pytestmark = pytest.mark.asyncio

#: More callers than the pool has connections.
#:
#: Two concurrent calls prove nothing here: each coroutine's chain of awaits
#: completes before the loop returns to the other, so the two reads never
#: overlap and an unlocked read-modify-write passes. Past the pool's size,
#: real connections are genuinely in flight together — which is both what
#: makes the race observable and what the hive actually does, every mind's
#: hook firing on its own turn boundary.
MERGERS = 24


@pytest.fixture
def owner() -> str:
    """One person's graph, named uniquely so tests cannot collide.

    The scratch database is session-scoped and nothing truncates between
    tests, and `memory_nodes_owner_type_name` is a real unique index — so a
    fixed owner would make the second test to run fail in its own setup.
    """
    return f"owner-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def a_name() -> str:
    return f"node-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def a_type(connected) -> str:
    """A registered node type, because `nodes.type` is a real foreign key.

    `memory.nodes.type` references `memory.schema_types(name)` ON DELETE
    RESTRICT, which SQLite never enforced — lucent's own store has no
    foreign keys on at all, since `lucent.py` never set the pragma.
    """
    name = f"Type{uuid.uuid4().hex[:8]}"
    await graph.type_put(name=name, kind="first-class", property_schema={})
    return name


async def test_a_written_node_is_on_disk_with_its_properties(
        connected, inspector, owner, a_name, a_type):
    written = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="",
        properties={"role": "operator", "city": "Houston"})

    row = await inspector.fetchrow(
        "SELECT owner, type, name, properties FROM memory.nodes "
        "WHERE id = $1", written["id"])
    assert row["owner"] == owner
    assert row["type"] == a_type
    assert row["name"] == a_name
    assert json.loads(row["properties"]) == {
        "role": "operator", "city": "Houston"}


async def test_writing_a_node_again_replaces_the_whole_blob_in_one_row(
        connected, inspector, owner, a_name, a_type):
    """Upsert is full-replace, and it replaces rather than duplicating.

    Two assertions in one test on purpose: "the old keys are gone" passes
    against an implementation that inserted a second row and read the newer
    one back, which is exactly the failure the unique index exists to
    prevent.
    """
    first = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="",
        properties={"role": "operator", "city": "Houston"})
    second = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="",
        properties={"role": "elder"})

    assert second["id"] == first["id"]
    rows = await inspector.fetch(
        "SELECT properties FROM memory.nodes "
        "WHERE owner = $1 AND type = $2 AND name = $3", owner, a_type, a_name)
    assert len(rows) == 1
    assert json.loads(rows[0]["properties"]) == {"role": "elder"}


async def test_a_node_with_no_owner_is_not_duplicated_by_a_second_write(
        connected, inspector, a_name, a_type):
    """The NULL-owner case the plain unique index does not cover.

    `memory_nodes_owner_type_name` is a plain btree, so two NULL owners are
    distinct to it and `ON CONFLICT (owner, type, name)` never fires. A Mind
    node is deliberately left ownerless until its credential is minted, and
    a duplicated Mind node is the identity fork `_check_identity_guard`
    exists to prevent.
    """
    first = await graph.node_write(
        owner=None, type=a_type, name=a_name, mind_id="", properties={"n": 1})
    second = await graph.node_write(
        owner=None, type=a_type, name=a_name, mind_id="", properties={"n": 2})

    assert second["id"] == first["id"]
    rows = await inspector.fetch(
        "SELECT properties FROM memory.nodes "
        "WHERE owner IS NULL AND type = $1 AND name = $2", a_type, a_name)
    assert len(rows) == 1
    assert json.loads(rows[0]["properties"]) == {"n": 2}


# Struck, and the reason is worth keeping: a test for "two concurrent writes
# of one node leave one row" was written here and could not be made to fail.
# Removing the advisory hold from `node_write` leaves the suite green at
# twenty-four concurrent writers over ten real backends, because the loop
# spreads the lookups far enough apart that the losers see the row the winner
# wrote and take the update path. Nothing in the new code can be edited to
# break it, so by the standard it does not get written. The hold stays in
# `node_write` — it makes the invariant true rather than lucky, and the
# NULL-owner test below is the one that does hold an edit accountable: with a
# plain `=` in place of `IS NOT DISTINCT FROM`, an ownerless node forks in two.


async def test_a_merge_adds_a_key_and_keeps_the_ones_already_there(
        connected, inspector, owner, a_name, a_type):
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="", properties={"role": "operator"})

    await graph.properties_merge(node_id=node["id"], additions={"city": "Houston"})

    row = await inspector.fetchrow(
        "SELECT properties FROM memory.nodes WHERE id = $1", node["id"])
    assert json.loads(row["properties"]) == {
        "role": "operator", "city": "Houston"}


async def test_concurrent_merges_keep_every_callers_keys(
        connected, inspector, owner, a_name, a_type):
    """The lost update that SQLite's one writer was hiding.

    `properties` is a text column, so a merge is a read, a decode, an update
    and a write. Without a lock held across those four, a caller reads
    `existing` before another's write lands and overwrites it — and both are
    told they succeeded, naming keys that are no longer on the node. This is
    the route `CLAUDE.local.md` tells the operator to prefer for additive
    updates.

    Two concurrent merges are not enough to show it: the event loop runs
    each short chain to completion and the reads do not overlap. The pool
    holds ten connections, so this drives more callers than there are
    connections — which is also the real shape, every mind's hook firing on
    its own turn boundary.
    """
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="",
        properties={"base": True})
    keys = [f"k{i}" for i in range(MERGERS)]

    await asyncio.gather(*(
        graph.properties_merge(node_id=node["id"], additions={key: i})
        for i, key in enumerate(keys)))

    row = await inspector.fetchrow(
        "SELECT properties FROM memory.nodes WHERE id = $1", node["id"])
    landed = json.loads(row["properties"])
    assert landed["base"] is True
    assert sorted(k for k in landed if k != "base") == sorted(keys)


async def test_an_edge_from_an_unregistered_mind_is_refused_by_name(
        connected, owner, a_type):
    """`memory.edges.mind_id` references `core.minds`; `nodes.mind_id` does not.

    So the node half of an upsert commits and the edge half fails, and the
    caller has to be told which parent is absent rather than handed the
    database's own sentence.
    """
    source = await graph.node_write(
        owner=owner, type=a_type, name=f"s-{uuid.uuid4().hex[:8]}",
        mind_id="", properties={})
    target = await graph.node_write(
        owner=owner, type=a_type, name=f"t-{uuid.uuid4().hex[:8]}",
        mind_id="", properties={})

    with pytest.raises(hive_data.MissingReference) as refused:
        await graph.edge_write(
            mind_id="not-a-registered-mind", owner=owner,
            source_id=source["id"], target_id=target["id"], type="KNOWS")

    assert "not-a-registered-mind" in str(refused.value)


async def test_a_soul_write_records_its_change_against_the_node(
        connected, inspector, owner, a_name, a_type):
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="", properties={})

    await graph.soul_change_record(
        node_id=node["id"], mind_name=a_name, mind_id=None,
        actor="daniel", reason="first", before={}, after={"a": 1})

    rows = await inspector.fetch(
        "SELECT node_id, actor, reason FROM memory.soul_changes "
        "WHERE node_id = $1", node["id"])
    assert len(rows) == 1
    assert rows[0]["node_id"] == node["id"]
    assert rows[0]["actor"] == "daniel"


async def test_a_soul_write_whose_record_fails_leaves_the_soul_alone(
        connected, inspector, owner, a_name, a_type):
    """The transaction SQLite was providing for free.

    `soul.py` updates the node then inserts the change row under one commit,
    and its docstring promises the record cannot drift from what was
    overwritten. The access layer is autocommit per operation, so without an
    explicit unit a dropped change row leaves a soul replaced with no
    provenance — and `change_count` then being one short makes the
    compare-and-set at the centre of the module pass when it should refuse.

    The record is made to fail by naming a node that is not there, which is
    the foreign key `soul_changes.node_id` already enforces.
    """
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="",
        properties={"soul_values": ["original"]})

    with pytest.raises(hive_data.MissingReference):
        await graph.soul_replace(
            node_id=node["id"], properties={"soul_values": ["replaced"]},
            record_against=-1, mind_name=a_name, mind_id=None,
            actor="daniel", reason="should roll back",
            before={"soul_values": ["original"]},
            after={"soul_values": ["replaced"]})

    row = await inspector.fetchrow(
        "SELECT properties FROM memory.nodes WHERE id = $1", node["id"])
    assert json.loads(row["properties"])["soul_values"] == ["original"]


async def test_soul_history_comes_back_newest_first(
        connected, owner, a_name, a_type):
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="", properties={})
    for reason in ("oldest", "middle", "newest"):
        await graph.soul_change_record(
            node_id=node["id"], mind_name=a_name, mind_id=None,
            actor="daniel", reason=reason, before={}, after={})

    history = await graph.soul_history(node_id=node["id"], limit=50)

    assert [h["reason"] for h in history] == ["newest", "middle", "oldest"]


async def test_the_stored_digest_resolves_and_a_revoked_one_does_not(
        connected, owner):
    holder = f"holder-{uuid.uuid4().hex[:8]}"
    digest = f"sha-{uuid.uuid4().hex}"
    await graph.credential_put(
        holder=holder, username=owner, role="mind",
        token_sha=digest, mind_id=None)

    assert (await graph.credential_by_token(token_sha=digest))["holder"] == holder

    await graph.credential_revoke(holder=holder)

    assert await graph.credential_by_token(token_sha=digest) is None


async def test_the_pruner_reads_the_rows_it_then_deletes(
        connected, inspector, a_mind):
    """The prune's read and its delete have to be the same store.

    Reading the retired SQLite file and deleting over HTTP is how a prune
    reports a clean run having deleted nothing, or deletes a row whose id
    the load renumbered.
    """
    data_class = f"class-{uuid.uuid4().hex[:8]}"
    kept = await hive_data.memory.store(
        mind_id=a_mind, content="keep me", data_class=data_class,
        tier="standing")
    doomed = await hive_data.memory.store(
        mind_id=a_mind, content="prune me", data_class=data_class,
        tier="contextual")

    entries = await graph.memories_for_class(
        data_class=data_class, include_standing=False)

    assert [e["id"] for e in entries] == [doomed["row"]["id"]]

    await hive_data.memory.delete(doomed["row"]["id"])
    remaining = await inspector.fetch(
        "SELECT id FROM memory.memories WHERE data_class = $1", data_class)
    assert [r["id"] for r in remaining] == [kept["row"]["id"]]


async def test_the_ownership_pass_claims_only_rows_that_have_no_owner(
        connected, inspector, owner, a_name, a_type):
    """The `WHERE owner IS NULL` is the arbitration, not a filter.

    Two passes running at once — two containers starting together — are two
    writers deciding one row, and the loser must not overwrite the claim the
    winner already made. A mind whose credential is minted after a boot is
    picked up at the next one, which is why the pass runs every time and has
    to be safe to run twice.
    """
    ownerless = await graph.node_write(
        owner=None, type=a_type, name=a_name, mind_id="writer-one",
        properties={})
    held = await graph.node_write(
        owner=owner, type=a_type, name=f"{a_name}-held", mind_id="writer-one",
        properties={})

    pending = await graph.unowned_rows()
    assert ownerless["id"] in [r["id"] for r in pending
                               if r["table"] == "memory.nodes"]
    assert held["id"] not in [r["id"] for r in pending]

    first = await graph.claim_owner(
        table="memory.nodes", row_id=ownerless["id"], owner="daniel")
    second = await graph.claim_owner(
        table="memory.nodes", row_id=ownerless["id"], owner="somebody-else")

    assert first["rows"] == 1
    assert second["rows"] == 0
    row = await inspector.fetchrow(
        "SELECT owner FROM memory.nodes WHERE id = $1", ownerless["id"])
    assert row["owner"] == "daniel"


async def test_the_ownership_pass_refuses_a_table_it_does_not_declare(
        connected):
    """The table name reaches a statement, so it is checked, not interpolated."""
    with pytest.raises(hive_data.ValueRefused):
        await graph.claim_owner(
            table="core.minds", row_id=1, owner="daniel")


async def test_a_soul_write_records_the_moment_the_caller_stamped_it(
        connected, inspector, owner, a_name, a_type):
    """The record exists to say what happened and when.

    Defaulting `at` to this write's own clock while the route reports back
    the stamp it was handed makes the one table that answers "when" disagree
    with the answer the caller was given.
    """
    node = await graph.node_write(
        owner=owner, type=a_type, name=a_name, mind_id="", properties={})

    await graph.soul_replace(
        node_id=node["id"], properties={"soul_values": ["a"]},
        mind_name=a_name, mind_id=None, actor="daniel", reason="stamped",
        before={}, after={"soul_values": ["a"]},
        at="2026-11-07T15:00:00+00:00", as_of="2026-11-07T15:00:00+00:00")

    change = await inspector.fetchrow(
        "SELECT at FROM memory.soul_changes WHERE node_id = $1", node["id"])
    node_row = await inspector.fetchrow(
        "SELECT as_of FROM memory.nodes WHERE id = $1", node["id"])
    assert change["at"] == "2026-11-07T15:00:00+00:00"
    assert node_row["as_of"] == "2026-11-07T15:00:00+00:00"
