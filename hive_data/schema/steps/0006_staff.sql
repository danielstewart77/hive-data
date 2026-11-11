--
-- Step 6: the chief of staff's ledger (stories 5.2.1 and 5.2.2).
--
-- What Daniel has handed the chief of staff to watch, and the hive-comms
-- sessions working each. Kept deliberately small: the chief of staff's
-- skills carry the behaviour, not the columns. There is no mind column (the
-- mind comes from the session), no board-link column (a board item is named
-- in the description text) and nothing recording how a session arrived.
--

SELECT pg_catalog.set_config('search_path', '', false);

CREATE SCHEMA staff;

COMMENT ON SCHEMA staff IS 'The chief of staff''s ledger: tasks it watches and the sessions working them.';

--
-- A task's status names a row here, so a status is added with an INSERT
-- rather than a migration, and a typo is refused by the key rather than
-- stored.
--
CREATE TABLE staff.statuses (
    name text NOT NULL,
    CONSTRAINT statuses_pkey PRIMARY KEY (name),
    CONSTRAINT statuses_name_not_blank CHECK (btrim(name) <> '')
);

INSERT INTO staff.statuses (name) VALUES
    ('in progress'), ('waiting on response'), ('on hold'), ('done');

CREATE TABLE staff.tasks (
    id text NOT NULL,
    name text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    status text NOT NULL,
    created_at double precision NOT NULL,
    updated_at double precision NOT NULL,
    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_name_not_blank CHECK (btrim(name) <> ''),
    -- ON UPDATE CASCADE so renaming a status relabels its tasks; RESTRICT on
    -- delete so a status still in use cannot vanish from under them.
    CONSTRAINT tasks_status_fk_statuses FOREIGN KEY (status)
        REFERENCES staff.statuses(name) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX tasks_status_idx ON staff.tasks USING btree (status);

--
-- A task paired with each session working it. Usually one pair; a bake-off
-- is several under one task. A session works one task at a time, so the
-- session id is the key, which is what makes "the task for a session" one
-- answer.
--
-- The session is `core.sessions.id`: the hive-comms session id, permanent
-- across rotations (a rotation rewrites the row's conversation id, never
-- its id). The only thing that removes it is the conversation being ended,
-- and the pair goes with it - RESTRICT here would make ending a
-- conversation that a task is watching fail inside comms.
--
CREATE TABLE staff.task_sessions (
    session_id text NOT NULL,
    task_id text NOT NULL,
    attached_at double precision NOT NULL,
    CONSTRAINT task_sessions_pkey PRIMARY KEY (session_id),
    CONSTRAINT task_sessions_task_id_fk_tasks FOREIGN KEY (task_id)
        REFERENCES staff.tasks(id) ON DELETE CASCADE,
    CONSTRAINT task_sessions_session_id_fk_sessions FOREIGN KEY (session_id)
        REFERENCES core.sessions(id) ON DELETE CASCADE
);

CREATE INDEX task_sessions_task_id_idx ON staff.task_sessions USING btree (task_id);
