from datetime import datetime, timezone
from .db import connect
from .honors import IMPORTANCE, URGENCY, medal_key

CATEGORIES = ('论文阅读', '算法复现', '实验分析', '工程支持', '分享整理', '设计', '开发', '文档', '调研', '运营', '其他')
STATUSES = {'open': '待认领', 'active': '进行中', 'review': '待验收', 'done': '已完成'}
KINDS = {'claim': '认领任务', 'submit': '提交成果', 'accept': '验收通过', 'return': '退回修改', 'comment': '讨论', 'settle': '历史结算记录'}

class InvalidAction(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def required(data, key, label, limit=10000):
    value = data.get(key, '').strip()
    if not value or len(value) > limit:
        raise InvalidAction(f'{label}不能为空，且不能超过 {limit} 字。')
    return value


def create_task(path, user_id, data):
    title = required(data, 'title', '标题', 120)
    description = required(data, 'description', '任务说明')
    requirements = required(data, 'requirements', '交付要求')
    category = data.get('category')
    importance = data.get('importance')
    urgency = data.get('urgency')
    if category not in CATEGORIES or importance not in IMPORTANCE or urgency not in URGENCY:
        raise InvalidAction('请选择有效的分类、任务分量和紧急程度。')
    try:
        deadline = datetime.fromisoformat(data.get('deadline', ''))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        deadline = deadline.astimezone(timezone.utc).isoformat(timespec='seconds')
        if deadline <= now():
            raise ValueError()
    except (ValueError, OverflowError):
        raise InvalidAction('请选择未来的截止时间（UTC）。')
    with connect(path, write=True) as db:
        cursor = db.execute('''INSERT INTO tasks
            (title,description,category,importance,urgency,deadline,requirements,owner_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (title, description, category, importance, urgency, deadline, requirements, user_id, now()))
        return cursor.lastrowid


def act(path, task_id, user_id, action, body=''):
    body = body.strip()
    if len(body) > 10000:
        raise InvalidAction('内容不能超过 10000 字。')
    with connect(path, write=True) as db:
        task = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not task:
            raise InvalidAction('任务不存在。')
        owner = task['owner_id'] == user_id
        assignee = task['assignee_id'] == user_id
        status = task['status']
        if action == 'claim':
            if owner or status != 'open' or task['deadline'] <= now():
                raise InvalidAction('无法认领：任务已被认领、已截止，或由你发布。')
            db.execute("UPDATE tasks SET assignee_id=?, status='active' WHERE id=?", (user_id, task_id))
            body = '已认领，开始处理。'
        elif action == 'submit':
            if not assignee or status != 'active' or not body:
                raise InvalidAction('仅认领人可提交进行中的任务，成果说明不能为空。')
            db.execute("UPDATE tasks SET status='review' WHERE id=?", (task_id,))
        elif action in ('accept', 'return'):
            if not owner or status != 'review':
                raise InvalidAction('仅发布者可验收待验收的任务。')
            if action == 'return' and not body:
                raise InvalidAction('请填写退回原因。')
            db.execute('UPDATE tasks SET status=? WHERE id=?', ('done' if action == 'accept' else 'active', task_id))
            body = body or '成果验收通过。'
            if action == 'accept':
                db.execute('INSERT INTO honors (task_id,user_id,medal_key,awarded_at) VALUES (?,?,?,?)',
                           (task_id, task['assignee_id'], medal_key(task), now()))
        elif action == 'comment':
            if not body:
                raise InvalidAction('讨论内容不能为空。')
        else:
            raise InvalidAction('未知操作。')
        db.execute('INSERT INTO events (task_id,user_id,kind,body,created_at) VALUES (?,?,?,?,?)',
                   (task_id, user_id, action, body, now()))
