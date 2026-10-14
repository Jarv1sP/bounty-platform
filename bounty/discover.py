"""Read-only queries behind the discovery page, the team feed and "my tasks"."""
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from .honors import MEDALS, medal_key
from .service import now


def _parse(value):
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def open_tasks(db, user_id):
    """Tasks this user could claim right now."""
    return db.execute('''SELECT t.*,u.name owner_name FROM tasks t JOIN users u ON u.id=t.owner_id
        WHERE t.status='open' AND t.owner_id<>? AND t.deadline>? ORDER BY t.deadline,t.id''', (user_id, now())).fetchall()


def earned_keys(db, user_id):
    return {row['medal_key'] for row in db.execute('SELECT medal_key FROM honors WHERE user_id=?', (user_id,))}


def tags_by_task(db, task_ids=None):
    """Tags per task in their original order. The whole table is small, so read it once and filter here."""
    wanted = None if task_ids is None else set(task_ids)
    tags = defaultdict(list)
    for row in db.execute('SELECT task_id,tag FROM task_tags ORDER BY rowid'):
        if wanted is None or row['task_id'] in wanted:
            tags[row['task_id']].append(row['tag'])
    return tags


def _grams(text):
    """Character bigrams: good enough to tell "造数据" tasks from "讲图论" tasks without any word list or model."""
    chars = [c for c in (text or '').lower() if c.isalnum()]
    return Counter(a + b for a, b in zip(chars, chars[1:]))


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(gram, 0) for gram, value in a.items())
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def profile(db, user_id):
    """What this person tends to pick up, built only from their own history, chosen interests and dismissals."""
    current = datetime.now(timezone.utc)
    history = db.execute('''SELECT t.id,t.title,t.description,t.project,h.awarded_at at,1.0 base FROM honors h
        JOIN tasks t ON t.id=h.task_id WHERE h.user_id=?
        UNION ALL SELECT t.id,t.title,t.description,t.project,t.created_at,0.5 FROM tasks t
        WHERE t.assignee_id=? AND t.status IN ('active','review')''', (user_id, user_id)).fetchall()
    tags_of = tags_by_task(db, [row['id'] for row in history])
    tag_weight, project_weight, tag_count, done_texts = Counter(), Counter(), Counter(), []
    for row in history:
        # 越近的经历越算数：两个月前做的任务权重减半
        weight = row['base'] * 0.5 ** ((current - _parse(row['at'])).days / 60)
        for tag in tags_of[row['id']]:
            tag_weight[tag] += weight
            tag_count[tag] += row['base'] == 1.0
        if row['project']:
            project_weight[row['project']] += weight
        if row['base'] == 1.0:
            done_texts.append((row['title'], _grams(row['title'] + row['description'])))
    interests = [row['tag'] for row in db.execute('SELECT tag FROM interests WHERE user_id=?', (user_id,))]
    for tag in interests:
        tag_weight[tag] += 1.5
    dismissed = {row['task_id'] for row in db.execute('SELECT task_id FROM dismissals WHERE user_id=?', (user_id,))}
    for tags in tags_by_task(db, list(dismissed)).values():
        for tag in tags:
            tag_weight[tag] -= 0.7
    texts = Counter()
    for _, grams in done_texts:
        texts.update(grams)
    return dict(tags=tag_weight, tag_count=tag_count, projects=project_weight, interests=set(interests),
                dismissed=dismissed, done_texts=done_texts, text=texts, earned=earned_keys(db, user_id))


def recommend(db, user_id, limit=3, batch=0):
    """Score every claimable task for one person and say why. Nothing is hard-coded per task or per category:
    new projects, tags and kinds of work join in automatically through their tags, project and wording."""
    me = profile(db, user_id)
    current = datetime.now(timezone.utc)
    tasks = [task for task in open_tasks(db, user_id) if task['id'] not in me['dismissed']]
    tags_of = tags_by_task(db, [task['id'] for task in tasks])
    project_start = {row['project']: row['first'] for row in db.execute(
        'SELECT project,MIN(created_at) first FROM tasks WHERE project IS NOT NULL GROUP BY project')}
    newcomer = len(me['done_texts']) < 3
    ranked = []
    for task in tasks:
        key, tags, reasons = medal_key(task), tags_of[task['id']], []
        score = 0.0
        # 1) 标签：你做过、正在做或说过想做的方向
        tag_score = sum(max(me['tags'][tag], 0) for tag in tags)
        if tag_score:
            score += min(tag_score, 3)
            best = max(tags, key=lambda tag: me['tags'][tag])
            if me['tag_count'][best]:
                reasons.append((min(tag_score, 3), 'skill', f'你做过 {me["tag_count"][best]} 个「{best}」任务'))
            elif best in me['interests']:
                reasons.append((min(tag_score, 3), 'interest', f'你说过想做「{best}」'))
        # 2) 项目：你参与过的项目，或者刚接进来的新项目
        if task['project'] and me['projects'][task['project']]:
            score += min(me['projects'][task['project']], 2) * 0.8
            reasons.append((1.5, 'project', f'你参与过「{task["project"]}」'))
        elif task['project'] and current - _parse(project_start[task['project']]) < timedelta(days=7):
            score += 0.8
            reasons.append((0.8, 'new-project', f'新项目「{task["project"]}」'))
        # 3) 文字相似：和你做过的任务说的是同一类事
        grams = _grams(task['title'] + task['description'])
        similarity = _cosine(grams, me['text'])
        if similarity > 0.12:
            score += similarity * 3
            closest = max(me['done_texts'], key=lambda item: _cosine(grams, item[1]))[0]
            reasons.append((similarity * 3, 'similar', f'和你做过的「{closest}」很像'))
        # 4) 勋章和时机
        if key not in me['earned']:
            score += 2
            reasons.append((2, 'unlock', '拿到你的第一枚勋章' if not me['earned'] else f'能解锁「{MEDALS[key]["name"]}」'))
        if task['urgency'] == 'urgent':
            score += 1.5
            reasons.append((1.5, 'urgent', '急需人手'))
        if newcomer and task['importance'] == 'light':
            score += 1
            reasons.append((1, 'quick', '半天能做完，适合先上手'))
        left = _parse(task['deadline']) - current
        if left < timedelta(days=2):
            score += 1
        if current - _parse(task['created_at']) < timedelta(days=2):
            score += 0.3
            reasons.append((0.3, 'fresh', '刚刚发布'))
        reasons.append((0, 'due', f'还有 {left.days} 天截止' if left.days else '今天截止'))
        # 卡片上先说和"你"有关的理由（做过、想做、参与过、内容像）：它们最能说明为什么是你，而不是人人都成立的那句
        personal = {'skill', 'interest', 'project', 'similar'}
        reasons.sort(key=lambda reason: -(reason[0] + (1.5 if reason[1] in personal else 0)))
        ranked.append((-score, task['deadline'], task['id'], task, [(kind, text) for _, kind, text in reasons], tags))
    ranked.sort(key=lambda item: item[:3])
    if not ranked:
        return []
    start = (batch * limit) % len(ranked)
    pool = [item[3:] for item in ranked[start:] + ranked[:start]]
    # 三张卡尽量各给一个不同的理由、不同的勋章，读起来才像"按你挑的"而不是同一句话说三遍
    picks, used_reasons, used_keys, taken = [], set(), set(), set()
    for strict in (True, False):
        for task, reasons, tags in pool:
            if task['id'] in taken:
                continue
            fresh = [reason for reason in reasons if reason[0] not in used_reasons]
            if strict and (not fresh or medal_key(task) in used_keys):
                continue
            chosen = (fresh or reasons)[0]
            picks.append(dict(task=task, tags=tags, reasons=[chosen] + [reason for reason in reasons if reason != chosen]))
            used_reasons.add(chosen[0])
            used_keys.add(medal_key(task))
            taken.add(task['id'])
            if len(picks) == limit:
                return picks
    return picks


def team_feed(db, viewer_id, limit=6):
    """Recent completions (with applause) and new tasks, newest first."""
    done = db.execute('''SELECT 'done' kind,e.created_at at,t.id task_id,t.title,a.name who,h.medal_key,
            (SELECT COUNT(*) FROM claps c WHERE c.task_id=t.id) claps,
            EXISTS(SELECT 1 FROM claps c WHERE c.task_id=t.id AND c.user_id=?) clapped,
            t.assignee_id=? mine
        FROM events e JOIN tasks t ON t.id=e.task_id JOIN users a ON a.id=t.assignee_id
        JOIN honors h ON h.task_id=t.id WHERE e.kind='accept' ORDER BY e.id DESC LIMIT ?''', (viewer_id, viewer_id, limit)).fetchall()
    posted = db.execute('''SELECT 'posted' kind,t.created_at at,t.id task_id,t.title,u.name who,
            t.importance || '-' || t.urgency medal_key,0 claps,0 clapped,0 mine
        FROM tasks t JOIN users u ON u.id=t.owner_id WHERE t.status='open' ORDER BY t.id DESC LIMIT ?''', (limit,)).fetchall()
    return sorted([dict(row) for row in (*done, *posted)], key=lambda row: row['at'], reverse=True)[:limit]


def week_summary(db):
    """Team completions this week (Monday UTC) against last week, plus a per-day histogram."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - timedelta(days=today.weekday())
    last_monday = monday - timedelta(days=7)
    days = [0] * 7
    this_week = last_week = 0
    for row in db.execute("SELECT created_at FROM events WHERE kind='accept' AND created_at>=?", (last_monday.isoformat(),)):
        moment = _parse(row['created_at'])
        if moment >= monday:
            this_week += 1
            days[(moment - monday).days] += 1
        else:
            last_week += 1
    return dict(count=this_week, previous=last_week, days=days, today=today.weekday())


def person_stats(db, user_id):
    row = db.execute('''SELECT COUNT(*) done, COUNT(DISTINCT t.owner_id) helped,
            (SELECT COUNT(*) FROM claps c JOIN tasks t2 ON t2.id=c.task_id WHERE t2.assignee_id=? AND t2.status='done') claps,
            (SELECT COUNT(*) FROM tasks WHERE owner_id=?) posted
        FROM honors h JOIN tasks t ON t.id=h.task_id WHERE h.user_id=?''', (user_id, user_id, user_id)).fetchone()
    return dict(row)


def my_tasks(db, user_id):
    """Group a person's tasks by whose move it is, newest activity first."""
    rows = db.execute('''SELECT t.*,u.name owner_name,a.name assignee_name,
            (SELECT kind FROM events e WHERE e.task_id=t.id ORDER BY e.id DESC LIMIT 1) last_kind,
            (SELECT body FROM events e WHERE e.task_id=t.id ORDER BY e.id DESC LIMIT 1) last_body,
            (SELECT x.name FROM events e JOIN users x ON x.id=e.user_id WHERE e.task_id=t.id ORDER BY e.id DESC LIMIT 1) last_name,
            (SELECT created_at FROM events e WHERE e.task_id=t.id ORDER BY e.id DESC LIMIT 1) last_at
        FROM tasks t JOIN users u ON u.id=t.owner_id LEFT JOIN users a ON a.id=t.assignee_id
        WHERE t.owner_id=? OR t.assignee_id=? ORDER BY COALESCE(last_at,t.created_at) DESC,t.id DESC''', (user_id, user_id)).fetchall()
    groups = {'yours': [], 'waiting': [], 'unclaimed': [], 'done': []}
    for task in rows:
        mine_to_do = task['assignee_id'] == user_id and task['status'] == 'active'
        mine_to_check = task['owner_id'] == user_id and task['status'] == 'review'
        if mine_to_do or mine_to_check:
            groups['yours'].append(task)
        elif task['status'] in ('active', 'review'):
            groups['waiting'].append(task)
        elif task['status'] == 'open':
            groups['unclaimed'].append(task)
        else:
            groups['done'].append(task)
    groups['done'] = groups['done'][:10]
    return groups
