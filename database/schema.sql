-- SQLite schema; see bounty/db.py for migrations.
-- Columns that bounty/db.py adds to older databases on startup:
--   tasks.project TEXT, tasks.cold INTEGER NOT NULL DEFAULT 0
--   honors.bonus INTEGER NOT NULL DEFAULT 0
--   users.title_key TEXT, users.notes_seen_at TEXT

CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, password TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
 category TEXT NOT NULL,
 importance TEXT NOT NULL CHECK(importance IN ('light','standard','major')),
 urgency TEXT NOT NULL CHECK(urgency IN ('normal','urgent')),
 deadline TEXT NOT NULL, requirements TEXT NOT NULL,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 assignee_id INTEGER REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','active','review','done')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
 user_id INTEGER NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS honors (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 medal_key TEXT NOT NULL,
 awarded_at TEXT NOT NULL, seen_at TEXT
);
CREATE INDEX IF NOT EXISTS honors_by_user ON honors(user_id);
CREATE TABLE IF NOT EXISTS featured_honors (
 user_id INTEGER NOT NULL REFERENCES users(id),
 slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
 medal_key TEXT NOT NULL,
 PRIMARY KEY(user_id,slot), UNIQUE(user_id,medal_key)
);
CREATE TABLE IF NOT EXISTS task_tags (
 task_id INTEGER NOT NULL REFERENCES tasks(id),
 tag TEXT NOT NULL,
 PRIMARY KEY(task_id,tag)
);
CREATE INDEX IF NOT EXISTS task_tags_by_tag ON task_tags(tag);
CREATE TABLE IF NOT EXISTS interests (
 user_id INTEGER NOT NULL REFERENCES users(id),
 tag TEXT NOT NULL,
 PRIMARY KEY(user_id,tag)
);
CREATE TABLE IF NOT EXISTS dismissals (
 user_id INTEGER NOT NULL REFERENCES users(id),
 task_id INTEGER NOT NULL REFERENCES tasks(id),
 created_at TEXT NOT NULL,
 PRIMARY KEY(user_id,task_id)
);
CREATE TABLE IF NOT EXISTS claps (
 task_id INTEGER NOT NULL REFERENCES tasks(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 PRIMARY KEY(task_id,user_id)
);
CREATE TABLE IF NOT EXISTS titles_seen (
 user_id INTEGER NOT NULL REFERENCES users(id),
 key TEXT NOT NULL,
 seen_at TEXT NOT NULL,
 PRIMARY KEY(user_id,key)
);
CREATE TABLE IF NOT EXISTS tickets (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 delta INTEGER NOT NULL,
 reason TEXT NOT NULL,
 task_id INTEGER REFERENCES tasks(id),
 ref TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tickets_by_user ON tickets(user_id);
CREATE TABLE IF NOT EXISTS game_runs (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 game TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT,
 score INTEGER,
 combo INTEGER
);
CREATE TABLE IF NOT EXISTS lines_solved (
 user_id INTEGER NOT NULL REFERENCES users(id),
 level INTEGER NOT NULL,
 solved_at TEXT NOT NULL,
 PRIMARY KEY(user_id,level)
);
