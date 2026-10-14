-- SQLite schema; see bounty/db.py for migrations.

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
