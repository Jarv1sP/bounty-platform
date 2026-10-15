import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

TASK_TABLE = '''CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
 category TEXT NOT NULL,
 importance TEXT NOT NULL CHECK(importance IN ('light','standard','major')),
 urgency TEXT NOT NULL CHECK(urgency IN ('normal','urgent')),
 deadline TEXT NOT NULL, requirements TEXT NOT NULL,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 assignee_id INTEGER REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','active','review','done')),
 created_at TEXT NOT NULL
)'''
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, password TEXT NOT NULL
);
''' + TASK_TABLE + ''';
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
CREATE TABLE IF NOT EXISTS game_runs (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 game TEXT NOT NULL,
 mode TEXT NOT NULL DEFAULT 'normal',
 started_at TEXT NOT NULL,
 finished_at TEXT,
 score INTEGER,
 combo INTEGER
);
CREATE TABLE IF NOT EXISTS daily_solved (
 user_id INTEGER NOT NULL REFERENCES users(id),
 day TEXT NOT NULL,
 solved_at TEXT NOT NULL,
 PRIMARY KEY(user_id,day)
);
CREATE TABLE IF NOT EXISTS builds (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 name TEXT NOT NULL,
 bg TEXT NOT NULL,
 parts TEXT NOT NULL,
 shown INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS builds_by_user ON builds(user_id);
CREATE TABLE IF NOT EXISTS lines_solved (
 user_id INTEGER NOT NULL REFERENCES users(id),
 level INTEGER NOT NULL,
 solved_at TEXT NOT NULL,
 PRIMARY KEY(user_id,level)
);
'''



@contextmanager
def connect(path, write=False):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        if write:
            db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    with connect(path) as db:
        db.execute('PRAGMA journal_mode = WAL')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(tasks)')}
        if 'reward' in columns:
            # Preserve the former monetary records in a one-time SQLite backup.
            backup = Path(str(path) + '.before-honors.bak')
            if not backup.exists():
                with closing(sqlite3.connect(backup)) as target:
                    db.backup(target)
            db.execute('PRAGMA foreign_keys = OFF')
            db.execute('BEGIN IMMEDIATE')
            db.execute(TASK_TABLE.replace('IF NOT EXISTS tasks', 'tasks_honors'))
            db.execute('''INSERT INTO tasks_honors
                (id,title,description,category,importance,urgency,deadline,requirements,
                 owner_id,assignee_id,status,created_at)
                SELECT id,title,description,category,'standard','normal',deadline,requirements,
                       owner_id,assignee_id,status,created_at FROM tasks''')
            db.execute('DROP TABLE tasks')
            db.execute('ALTER TABLE tasks_honors RENAME TO tasks')
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('数据库迁移失败：存在无效归属。')
            db.commit()
            db.execute('PRAGMA foreign_keys = ON')
        tables = {row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # 早期版本的「游戏券」账本：游戏角现在改成用勋章解锁，这张表只是从勋章推出来的，直接去掉
        db.execute('DROP TABLE IF EXISTS tickets')
        if 'game_runs' in tables and 'mode' not in {row['name'] for row in db.execute('PRAGMA table_info(game_runs)')}:
            db.execute("ALTER TABLE game_runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'normal'")
        db.executescript(SCHEMA)
        if 'seen_at' not in {row['name'] for row in db.execute('PRAGMA table_info(honors)')}:
            db.execute('ALTER TABLE honors ADD COLUMN seen_at TEXT')
        task_columns = {row['name'] for row in db.execute('PRAGMA table_info(tasks)')}
        if 'project' not in task_columns:
            db.execute('ALTER TABLE tasks ADD COLUMN project TEXT')
        if 'cold' not in task_columns:   # 等了好几天才有人接的任务，完成时多给经验
            db.execute('ALTER TABLE tasks ADD COLUMN cold INTEGER NOT NULL DEFAULT 0')
        if 'bonus' not in {row['name'] for row in db.execute('PRAGMA table_info(honors)')}:
            db.execute('ALTER TABLE honors ADD COLUMN bonus INTEGER NOT NULL DEFAULT 0')
        user_columns = {row['name'] for row in db.execute('PRAGMA table_info(users)')}
        if 'title_key' not in user_columns:
            db.execute('ALTER TABLE users ADD COLUMN title_key TEXT')
        if 'play_seen' not in user_columns:   # 上次进游戏角时已经解锁了哪些：多出来的在导航上标「新」
            db.execute("ALTER TABLE users ADD COLUMN play_seen TEXT NOT NULL DEFAULT ''")
        if 'notes_seen_at' not in user_columns:
            # 老用户从现在开始收纸条，不把以前的鼓掌一股脑翻出来
            db.execute('ALTER TABLE users ADD COLUMN notes_seen_at TEXT')
            db.execute("UPDATE users SET notes_seen_at=strftime('%Y-%m-%dT%H:%M:%S+00:00','now')")
        # Older tasks had one fixed category; it becomes their first tag so search and recommendations keep working.
        db.execute('INSERT OR IGNORE INTO task_tags (task_id,tag) SELECT id,category FROM tasks WHERE id NOT IN (SELECT task_id FROM task_tags)')
        # Also resumes safely if startup was interrupted after the table migration.
        db.execute('''INSERT OR IGNORE INTO honors (task_id,user_id,medal_key,awarded_at)
            SELECT t.id,t.assignee_id,t.importance || '-' || t.urgency,
                   COALESCE((SELECT MAX(created_at) FROM events WHERE task_id=t.id AND kind='accept'),t.created_at)
            FROM tasks t WHERE t.status='done' AND t.assignee_id IS NOT NULL''')
