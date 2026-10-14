"""Team activity, personal focus, and appreciation for verified deliveries."""
from .db import connect
from .service import InvalidAction, now

TASK_PEOPLE = '''SELECT t.*, owner.name owner_name, worker.name assignee_name
    FROM tasks t JOIN users owner ON owner.id=t.owner_id
    LEFT JOIN users worker ON worker.id=t.assignee_id'''


def recent_activity(path, limit=5):
    with connect(path) as db:
        return db.execute('''SELECT e.kind,e.created_at,u.name,t.id task_id,t.title
            FROM events e JOIN users u ON u.id=e.user_id JOIN tasks t ON t.id=e.task_id
            WHERE e.kind IN ('claim','submit','accept') ORDER BY e.id DESC LIMIT ?''', (limit,)).fetchall()


def workbench(path, user_id):
    with connect(path) as db:
        review = db.execute(TASK_PEOPLE + " WHERE t.owner_id=? AND t.status='review' ORDER BY t.deadline,t.id", (user_id,)).fetchall()
        claimed = db.execute(TASK_PEOPLE + " WHERE t.assignee_id=? AND t.status IN ('active','review') ORDER BY t.deadline,t.id", (user_id,)).fetchall()
        returned = {row['task_id']: row['body'] for row in db.execute('''SELECT e.task_id,e.body FROM events e
            JOIN tasks t ON t.id=e.task_id WHERE t.assignee_id=? AND t.status='active' AND e.kind='return'
            AND e.id=(SELECT MAX(id) FROM events WHERE task_id=t.id AND kind IN ('submit','return','accept'))''', (user_id,))}
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE assignee_id=? AND status='done'", (user_id,)).fetchone()[0]
        published = db.execute('SELECT COUNT(*) FROM tasks WHERE owner_id=?', (user_id,)).fetchone()[0]
    return dict(review=review, claimed=claimed, returned=returned, completed=completed, published=published)


def team_results(path, user_id, page=1, page_size=12):
    with connect(path) as db:
        total = db.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, pages))
        results = db.execute('''SELECT t.*,owner.name owner_name,worker.name assignee_name,
            h.medal_key,h.awarded_at,
            (SELECT body FROM events WHERE task_id=t.id AND kind='submit' ORDER BY id DESC LIMIT 1) delivery,
            (SELECT body FROM events WHERE task_id=t.id AND kind='accept' ORDER BY id DESC LIMIT 1) acceptance,
            (SELECT COUNT(*) FROM appreciations WHERE task_id=t.id) appreciation_count,
            EXISTS(SELECT 1 FROM appreciations WHERE task_id=t.id AND user_id=?) appreciated
            FROM tasks t JOIN users owner ON owner.id=t.owner_id
            JOIN users worker ON worker.id=t.assignee_id JOIN honors h ON h.task_id=t.id
            WHERE t.status='done' ORDER BY h.awarded_at DESC,t.id DESC LIMIT ? OFFSET ?''',
            (user_id, page_size, (page - 1) * page_size)).fetchall()
        contributors = db.execute("SELECT COUNT(DISTINCT assignee_id) FROM tasks WHERE status='done'").fetchone()[0]
        active = db.execute("SELECT COUNT(*) FROM tasks WHERE status='active'").fetchone()[0]
    return dict(results=results, total=total, contributors=contributors, active=active, page=page, pages=pages)


def appreciation_state(path, task_id, user_id):
    with connect(path) as db:
        count = db.execute('SELECT COUNT(*) FROM appreciations WHERE task_id=?', (task_id,)).fetchone()[0]
        mine = db.execute('SELECT 1 FROM appreciations WHERE task_id=? AND user_id=?', (task_id, user_id)).fetchone() is not None
    return dict(appreciation_count=count, appreciated=mine)


def toggle_appreciation(path, task_id, user_id):
    with connect(path, write=True) as db:
        task = db.execute('SELECT status,assignee_id FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not task or task['status'] != 'done':
            raise InvalidAction('任务验收通过后才能标记有帮助。')
        if task['assignee_id'] == user_id:
            raise InvalidAction('不能为自己的成果标记有帮助。')
        existing = db.execute('SELECT 1 FROM appreciations WHERE task_id=? AND user_id=?', (task_id, user_id)).fetchone()
        if existing:
            db.execute('DELETE FROM appreciations WHERE task_id=? AND user_id=?', (task_id, user_id))
        else:
            db.execute('INSERT INTO appreciations(task_id,user_id,created_at) VALUES(?,?,?)', (task_id, user_id, now()))
        count = db.execute('SELECT COUNT(*) FROM appreciations WHERE task_id=?', (task_id,)).fetchone()[0]
    return dict(appreciated=not bool(existing), appreciation_count=count)
