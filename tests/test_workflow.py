import concurrent.futures
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from app import create_app
from bounty.db import connect, initialize
from bounty import discover, progress
from bounty.service import InvalidAction, act, clap, create_task, dismiss, parse_tags, set_interests
from bounty.honors import MEDALS, medal_key


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test'})
        self.clients = []
        for name in ('owner', 'worker', 'other'):
            client = self.app.test_client()
            self.post(client, '/auth/register', {'name': name, 'password': 'test-password'})
            self.clients.append(client)
        self.data = dict(title='入门文档', description='整理团队知识', requirements='交付文档链接',
                         category='文档', importance='standard', urgency='normal',
                         deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
        self.task_id = create_task(self.path, 1, self.data)

    def tearDown(self):
        self.temp.cleanup()

    def post(self, client, path, data):
        client.get('/auth/login')
        with client.session_transaction() as session:
            csrf = session['csrf']
        return client.post(path, data={**data, 'csrf': csrf}, follow_redirects=True)

    def test_workflow_through_pages(self):
        owner, worker, other = self.clients
        base = f'/tasks/{self.task_id}'
        self.assertIn('入门文档', owner.get('/?category=文档').text)
        self.assertIn('入门文档', owner.get('/?tag=文档').text)
        self.assertNotIn('入门文档', other.get('/mine').text)
        self.post(worker, base + '/claim', {})
        self.assertIn('入门文档', worker.get('/mine').text)
        self.post(worker, base + '/submit', {'body': '第一版 https://example.test/doc'})
        result = self.post(owner, base + '/return', {'body': ''})
        self.assertIn('请填写退回原因', result.text)
        self.post(owner, base + '/return', {'body': '补充安装步骤'})
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM honors').fetchone()[0], 0)
        self.post(worker, base + '/submit', {'body': '修订版，已补充安装步骤'})
        self.post(owner, base + '/accept', {})
        self.assertIn('class="tile" data-collection-key="standard-normal"', worker.get('/honors').text)
        self.assertIn('入门文档', worker.get('/honors').text)
        self.assertNotIn('入门文档', other.get('/honors').text)
        with connect(self.path) as db:
            award = db.execute('SELECT * FROM honors').fetchone()
            self.assertEqual((award['user_id'], award['medal_key']), (2, 'standard-normal'))
        page = self.post(other, base + '/comment', {'body': '<script>alert(1)</script>'})
        self.assertIn('已授予 worker', page.text)
        self.assertIn('第一版', page.text)
        self.assertIn('补充安装步骤', page.text)
        self.assertIn('&lt;script&gt;', page.text)
        self.assertNotIn('<script>alert', page.text)
        with self.assertRaises(InvalidAction):
            act(self.path, self.task_id, 1, 'settle', '重复')

    def test_owner_and_state_guards(self):
        for uid, action in ((1, 'claim'), (3, 'submit'), (3, 'accept'), (3, 'settle')):
            with self.assertRaises(InvalidAction):
                act(self.path, self.task_id, uid, action, '越权')
        act(self.path, self.task_id, 2, 'claim')
        for uid, action in ((3, 'submit'), (2, 'accept'), (1, 'accept'), (3, 'return')):
            with self.assertRaises(InvalidAction):
                act(self.path, self.task_id, uid, action, '越权')
        act(self.path, self.task_id, 2, 'submit', '成果')
        for action in ('accept', 'return', 'settle'):
            with self.assertRaises(InvalidAction):
                act(self.path, self.task_id, 3, action, '越权')
        act(self.path, self.task_id, 1, 'accept')
        with self.assertRaises(InvalidAction):
            act(self.path, self.task_id, 2, 'settle', '越权')

    def test_concurrent_claim_has_one_winner(self):
        def claim(uid):
            try:
                act(self.path, self.task_id, uid, 'claim')
                return True
            except InvalidAction:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, [2, 3]))
        self.assertEqual(sum(results), 1)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 1)
            self.assertIn(db.execute('SELECT assignee_id FROM tasks').fetchone()[0], (2, 3))

    def test_validation_deadline_and_priority(self):
        for patch in ({'importance': 'invalid'}, {'importance': ''}, {'urgency': 'invalid'},
                      {'urgency': ''}, {'deadline': 'bad'},
                      {'deadline': '2020-01-01T00:00'}, {'title': ''}):
            with self.assertRaises(InvalidAction):
                create_task(self.path, 1, {**self.data, **patch})
        with connect(self.path, write=True) as db:
            db.execute("UPDATE tasks SET deadline='2020-01-01T00:00:00+00:00'")
        with self.assertRaises(InvalidAction):
            act(self.path, self.task_id, 2, 'claim')

    def test_medal_mapping_and_duplicate_acceptance(self):
        for key in MEDALS:
            importance, urgency = key.split('-')
            task_id = create_task(self.path, 1, {**self.data, 'importance': importance,
                                                'urgency': urgency, 'medal_key': 'fake'})
            with connect(self.path) as db:
                task = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
                self.assertEqual(medal_key(task), key)
            act(self.path, task_id, 2, 'claim')
            act(self.path, task_id, 2, 'submit', '交付')
            def accept(_):
                try:
                    act(self.path, task_id, 1, 'accept')
                    return True
                except InvalidAction:
                    return False
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(sum(executor.map(accept, [1, 2])), 1)
            with connect(self.path) as db:
                awards = db.execute('SELECT * FROM honors WHERE task_id=?', (task_id,)).fetchall()
                self.assertEqual(len(awards), 1)
                self.assertEqual(awards[0]['medal_key'], key)
        initialize(self.path)
        initialize(self.path)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM honors').fetchone()[0], 6)
        self.assertEqual(self.clients[1].get('/honors').status_code, 200)

    def test_legacy_migration_keeps_accounts_and_tasks(self):
        legacy = str(Path(self.temp.name) / 'legacy.db')
        with connect(legacy) as db:
            db.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,password TEXT);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT,description TEXT,category TEXT,
                  reward INTEGER NOT NULL,reward_type TEXT NOT NULL,deadline TEXT,requirements TEXT,
                  owner_id INTEGER REFERENCES users(id),assignee_id INTEGER REFERENCES users(id),
                  status TEXT,created_at TEXT,settled_at TEXT,settlement_note TEXT);
                CREATE TABLE events(id INTEGER PRIMARY KEY,task_id INTEGER REFERENCES tasks(id),
                  user_id INTEGER REFERENCES users(id),kind TEXT,body TEXT,created_at TEXT);
                INSERT INTO users VALUES(1,'publisher','hash'),(2,'worker','hash');
                INSERT INTO tasks VALUES(1,'old task','description','文档',1000,'CNY','2027-01-01',
                  'doc',1,2,'done','2026-01-01',NULL,NULL);
                INSERT INTO events VALUES(1,1,1,'accept','accepted','2026-01-02');
            """)
        initialize(legacy)
        initialize(legacy)
        with connect(legacy) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT title FROM tasks').fetchone()[0], 'old task')
            award = db.execute('SELECT * FROM honors').fetchone()
            self.assertEqual((award['user_id'], award['medal_key'], award['awarded_at']),
                             (2, 'standard-normal', '2026-01-02'))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM honors').fetchone()[0], 1)
        with connect(legacy + '.before-honors.bak') as db:
            self.assertEqual(db.execute('SELECT reward FROM tasks').fetchone()[0], 1000)

    def test_success_feedback_is_confirmed_and_consumed(self):
        owner, worker, other = self.clients
        base = f'/tasks/{self.task_id}'
        failed = self.post(owner, base + '/claim', {})
        self.assertNotIn('data-confirmed-action=', failed.text)
        claimed = self.post(worker, base + '/claim', {})
        self.assertIn('data-confirmed-action="claim"', claimed.text)
        self.assertNotIn('data-confirmed-action=', worker.get(base).text)
        failed = self.post(other, base + '/submit', {'body': 'not my task'})
        self.assertNotIn('data-confirmed-action=', failed.text)
        submitted = self.post(worker, base + '/submit', {'body': '成果'})
        self.assertIn('data-confirmed-action="submit"', submitted.text)

    def test_reveal_is_private_and_atomic(self):
        act(self.path, self.task_id, 2, 'claim')
        act(self.path, self.task_id, 2, 'submit', '成果')
        act(self.path, self.task_id, 1, 'accept')
        self.assertEqual(self.post(self.clients[0], '/honors/reveal', {}).json['awards'], [])
        clients = [self.app.test_client(), self.app.test_client()]
        for client in clients:
            with client.session_transaction() as session:
                session.update(user_id=2, csrf='test')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            batches = list(executor.map(lambda client: client.post('/honors/reveal',
                data={'csrf': 'test', 'user_id': '3'}).json['awards'], clients))
        self.assertEqual(sum(len(batch) for batch in batches), 1)
        self.assertEqual(self.post(self.clients[1], '/honors/reveal', {}).json['awards'], [])
        initialize(self.path)
        self.assertEqual(self.post(self.clients[1], '/honors/reveal', {}).json['awards'], [])
        self.assertEqual(self.clients[1].post('/honors/reveal').status_code, 400)

    def test_featured_medals_are_owned_and_limited(self):
        keys = list(MEDALS)[:4]
        for key in keys:
            importance, urgency = key.split('-')
            task_id = create_task(self.path, 1, {**self.data, 'importance': importance, 'urgency': urgency})
            act(self.path, task_id, 2, 'claim')
            act(self.path, task_id, 2, 'submit', '成果')
            act(self.path, task_id, 1, 'accept')
        self.post(self.clients[1], '/honors/featured', {'medals': keys[:3]})
        rejected = self.post(self.clients[1], '/honors/featured', {'medals': keys})
        self.assertIn('最多展示三种', rejected.text)
        rejected = self.post(self.clients[2], '/honors/featured', {'medals': keys[:1]})
        self.assertIn('只能展示自己已获得', rejected.text)
        with connect(self.path) as db:
            featured = db.execute('SELECT * FROM featured_honors ORDER BY slot').fetchall()
            self.assertEqual([row['medal_key'] for row in featured], keys[:3])
            self.assertTrue(all(row['user_id'] == 2 for row in featured))
        self.post(self.clients[1], '/honors/featured', {})
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM featured_honors').fetchone()[0], 0)

    def test_local_data_directory_session_restart_and_csrf(self):
        directory = Path(self.temp.name) / '独立 数据'
        first = create_app({'TESTING': True, 'DATA_DIR': str(directory)})
        client = first.test_client()
        self.post(client, '/auth/register', {'name': '本地成员', 'password': 'local-password'})
        self.assertTrue((directory / 'bounty.sqlite3').exists())
        self.assertTrue((directory / 'secret.key').exists())
        second = create_app({'TESTING': True, 'DATA_DIR': str(directory)})
        restored = second.test_client()
        restored.set_cookie('session', client.get_cookie('session').value)
        self.assertIn('本地成员', restored.get('/').text)
        self.assertEqual(restored.post('/logout', data={'csrf': '无效令牌'}).status_code, 400)

    def test_demo_database_is_independent_and_idempotent_safe(self):
        from bounty.demo import seed_demo
        path = str(Path(self.temp.name) / 'demo.sqlite3')
        self.assertEqual(seed_demo(path), 27)
        with self.assertRaises(ValueError):
            seed_demo(path)
        with connect(path) as db:
            counts = dict(db.execute('SELECT status,COUNT(*) FROM tasks GROUP BY status').fetchall())
            self.assertEqual(counts, {'open': 15, 'active': 3, 'review': 2, 'done': 7})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM honors').fetchone()[0], 7)
            # 演示里有一部分勋章已经拆开过，其余留在信箱里等颁奖
            self.assertEqual(db.execute('SELECT COUNT(*) FROM honors WHERE seen_at IS NULL').fetchone()[0], 4)
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT project) FROM tasks').fetchone()[0], 5)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        app = create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test'})
        client = app.test_client()
        self.post(client, '/auth/login', {'name': '认领人', 'password': 'demo12345'})
        response = client.get('/')
        # 发现页默认只列可认领的任务，一页 12 个
        self.assertEqual(response.text.count('data-task='), 15)
        self.assertEqual(response.text.count('class="wall-zone"'), 2)
        # 演示账号「认领人」选过方向：两排推荐各三张，互不重复
        picks = response.text.split('data-lane-body="want"')[1]
        want, past = picks.split('data-lane-body="past"')
        self.assertEqual(want.count('data-pick='), 3)
        self.assertEqual(past.count('data-pick='), 3)
        ids = lambda html: {part.split('"')[0] for part in html.split('data-pick="')[1:]}
        self.assertFalse(ids(want) & ids(past.split('class="wall"')[0]))

    def test_auth_csrf_and_persistence(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/tasks/new').status_code, 302)
        self.assertEqual(client.post(f'/tasks/{self.task_id}/claim').status_code, 400)
        self.assertIn('用户名或密码不正确', self.post(client, '/auth/login', {'name': 'owner', 'password': 'wrong-password'}).text)
        self.post(client, '/auth/login', {'name': 'owner', 'password': 'test-password'})
        result = self.post(client, '/tasks/new', {**self.data, 'title': '新任务'})
        self.assertIn('新任务', result.text)
        second_app = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test'})
        with connect(second_app.config['DATABASE']) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 2)
            self.assertNotEqual(db.execute('SELECT password FROM users WHERE id=1').fetchone()[0], 'test-password')

    def finish(self, task_id, worker=2, owner=1, body=''):
        act(self.path, task_id, worker, 'claim')
        act(self.path, task_id, worker, 'submit', '成果')
        act(self.path, task_id, owner, 'accept', body)

    def test_tags_and_projects_are_free_form(self):
        self.assertEqual(parse_tags('数据, 图论，PyTorch、 #校赛  数据'), ['数据', '图论', 'PyTorch', '校赛'])
        for raw in ('a b c d e f', '这个标签实在是太长了超过了十六个字的限制'):
            with self.assertRaises(InvalidAction):
                parse_tags(raw)
        with self.assertRaises(InvalidAction):
            create_task(self.path, 1, {**self.data, 'category': '', 'tags': ''})
        task_id = create_task(self.path, 1, {**self.data, 'title': '造模拟赛数据', 'tags': '数据 图论', 'project': '校赛 2026'})
        with connect(self.path) as db:
            self.assertEqual(discover.tags_by_task(db, [task_id])[task_id], ['数据', '图论'])
        owner = self.clients[0]
        card = f'data-task="{task_id}"'
        self.assertIn(card, owner.get('/?tag=图论').text)
        self.assertNotIn(card, owner.get('/?tag=文档').text)
        self.assertIn(card, owner.get('/?project=校赛 2026').text)
        self.assertIn('#图论', owner.get('/').text)

    def test_recommendations_follow_history_interests_and_dismissals(self):
        data_task = create_task(self.path, 1, {**self.data, 'title': '清洗比赛提交记录', 'description': '去掉重复提交和测试账号', 'tags': '数据'})
        self.finish(data_task)
        similar = create_task(self.path, 1, {**self.data, 'title': '清洗题目标签', 'description': '去掉重复和错标的标签', 'tags': '数据'})
        graph = create_task(self.path, 1, {**self.data, 'title': '讲一次图论', 'tags': '图论', 'project': '新人培养'})
        with connect(self.path) as db:
            picks = {pick['task']['id']: dict(pick['reasons']) for pick in discover.recommend(db, 2, limit=10)}
        self.assertIn('skill', picks[similar])
        self.assertIn('new-project', picks[graph])
        set_interests(self.path, 3, '图论')
        with connect(self.path) as db:
            first = discover.recommend(db, 3, limit=1)[0]
        self.assertEqual(first['task']['id'], graph)
        self.assertEqual(first['reasons'][0][0], 'interest')
        dismiss(self.path, graph, 3)
        with connect(self.path) as db:
            self.assertNotIn(graph, [pick['task']['id'] for pick in discover.recommend(db, 3, limit=10)])
            # 自己发布的任务不会推荐给自己
            self.assertFalse(discover.recommend(db, 1, limit=10))

    def test_claps_are_once_per_teammate_and_never_for_yourself(self):
        with self.assertRaises(InvalidAction):
            clap(self.path, self.task_id, 3)
        self.finish(self.task_id)
        with self.assertRaises(InvalidAction):
            clap(self.path, self.task_id, 2)
        self.assertEqual(clap(self.path, self.task_id, 3), 1)
        self.assertEqual(clap(self.path, self.task_id, 3), 1)
        other = self.clients[2]
        other.get('/')
        with other.session_transaction() as session:
            csrf = session['csrf']
        response = other.post(f'/tasks/{self.task_id}/clap', data={'csrf': csrf}, headers={'Accept': 'application/json'})
        self.assertEqual(response.json, {'claps': 1})
        with connect(self.path) as db:
            self.assertEqual(discover.person_stats(db, 2)['claps'], 1)

    def test_experience_levels_and_reveal_tiers(self):
        self.assertEqual([progress.level_floor(n) for n in (1, 2, 3, 4)], [0, 50, 150, 300])
        self.assertEqual(progress.task_xp('light-normal'), 10)
        self.assertEqual(progress.task_xp('major-urgent'), 120)
        self.assertEqual(progress.level_info(49)['level'], 1)
        self.assertEqual(progress.level_info(50)['level'], 2)
        for key in ('light-normal', 'standard-normal', 'major-normal', 'light-normal'):
            importance, urgency = key.split('-')
            self.finish(create_task(self.path, 1, {**self.data, 'importance': importance, 'urgency': urgency}), body='写得很清楚')
        worker = self.clients[1]
        worker.get('/honors')
        with worker.session_transaction() as session:
            csrf = session['csrf']
        result = worker.post('/honors/reveal', data={'csrf': csrf}).json
        self.assertEqual([award['tier'] for award in result['awards']], ['new', 'new', 'row', 'plain'])
        self.assertEqual(result['awards'][2]['row'], '冷色一行')
        self.assertEqual(result['awards'][0]['praise'], '写得很清楚')
        self.assertEqual((result['before']['level'], result['after']['level'], result['after']['xp']), (1, 2, 130))
        with connect(self.path) as db:
            self.assertTrue(progress.person_progress(db, 2)['rows']['normal'])

    def test_team_bundle_fills_matching_slots(self):
        honors = [{'medal_key': key} for key in ('light-urgent', 'standard-normal', 'major-normal', 'light-normal')]
        filled = progress._fill(('urgent', 'standard', 'light'), honors)
        self.assertEqual([honor['medal_key'] for honor in filled], ['light-urgent', 'standard-normal', 'light-normal'])
        self.assertEqual(progress._fill(('major', 'major'), honors)[1], None)
        self.finish(self.task_id)
        with connect(self.path) as db:
            bundles = progress.team_bundles(db)
        self.assertEqual(len(bundles['current']['slots']), 3)
        self.assertLessEqual(bundles['pieces'], bundles['piece_count'])

    def test_naive_deadline_uses_team_timezone(self):
        moment = datetime.now(timezone.utc) + timedelta(days=3)
        naive = moment.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None).isoformat(timespec='minutes')
        task_id = create_task(self.path, 1, {**self.data, 'deadline': naive})
        with connect(self.path) as db:
            stored = datetime.fromisoformat(db.execute('SELECT deadline FROM tasks WHERE id=?', (task_id,)).fetchone()[0])
        self.assertLess(abs((stored - moment).total_seconds()), 61)

    def test_my_tasks_group_by_whose_move_it_is(self):
        returned = create_task(self.path, 1, {**self.data, 'title': '被退回的任务'})
        act(self.path, returned, 2, 'claim')
        act(self.path, returned, 2, 'submit', '第一版')
        act(self.path, returned, 1, 'return', '补测试')
        waiting = create_task(self.path, 1, {**self.data, 'title': '等验收的任务'})
        act(self.path, waiting, 2, 'claim')
        act(self.path, waiting, 2, 'submit', '成果')
        with connect(self.path) as db:
            worker = discover.my_tasks(db, 2)
            owner = discover.my_tasks(db, 1)
        self.assertEqual([task['title'] for task in worker['yours']], ['被退回的任务'])
        self.assertEqual(worker['yours'][0]['last_kind'], 'return')
        self.assertEqual([task['title'] for task in worker['waiting']], ['等验收的任务'])
        self.assertIn('等验收的任务', [task['title'] for task in owner['yours']])
        self.assertIn('入门文档', [task['title'] for task in owner['unclaimed']])
        page = self.clients[1].get('/mine').text
        self.assertIn('被退回，等你改', page)

    def test_two_lanes_keep_picked_directions_apart_from_history(self):
        data_task = create_task(self.path, 1, {**self.data, 'title': '清洗比赛提交记录', 'description': '去掉重复提交', 'tags': '数据'})
        self.finish(data_task)
        more_data = create_task(self.path, 1, {**self.data, 'title': '清洗题目标签', 'description': '去掉重复标签', 'tags': '数据'})
        graph = create_task(self.path, 1, {**self.data, 'title': '讲一次图论', 'tags': '图论'})
        set_interests(self.path, 2, '图论')
        with connect(self.path) as db:
            want = discover.recommend(db, 2, limit=10, lane='want')
            past = discover.recommend(db, 2, limit=10, lane='past', exclude={pick['task']['id'] for pick in want})
            self.assertEqual([pick['task']['id'] for pick in want], [graph])
            self.assertEqual(want[0]['reasons'][0], ('interest', '你选了「图论」'))
            self.assertNotIn(graph, [pick['task']['id'] for pick in past])
            # 第二排先放和你经历有关的任务，理由里不出现"你选了"
            self.assertEqual(past[0]['task']['id'], more_data)
            self.assertEqual(past[0]['reasons'][0][0], 'skill')
            self.assertFalse(any(kind == 'interest' for pick in past for kind, _ in pick['reasons']))
            self.assertEqual(discover.past_tags(db, 2), [('数据', 1)])
            options = {option['tag']: option for option in discover.directions(db, ['图论', '冷门方向'])}
            self.assertTrue(options['图论']['chosen'])
            self.assertEqual(options['图论']['example'], '讲一次图论')
            self.assertEqual(options['冷门方向']['count'], 0)
        worker = self.clients[1]
        home = worker.get('/').text
        self.assertIn('按你选的方向', home)
        self.assertIn('你常做', home)
        self.assertIn('data-lane-body="want"', worker.get('/picks/want').text)
        self.assertIn('讲一次图论', worker.get('/picks/want').text)
        self.assertNotIn('讲一次图论', worker.get('/picks/past').text)
        self.assertEqual(worker.get('/picks/other').status_code, 404)

    def test_directions_can_be_repicked_any_time(self):
        worker = self.clients[1]
        worker.get('/')
        with worker.session_transaction() as session:
            csrf = session['csrf']
        saved = worker.post('/me/interests', data={'csrf': csrf, 'tags': ['图论', '数据']}, headers={'Accept': 'application/json'})
        self.assertEqual(saved.json, {'interests': ['图论', '数据']})
        saved = worker.post('/me/interests', data={'csrf': csrf, 'tags': ['论文']}, headers={'Accept': 'application/json'})
        self.assertEqual(saved.json, {'interests': ['论文']})
        cleared = worker.post('/me/interests', data={'csrf': csrf}, headers={'Accept': 'application/json'})
        self.assertEqual(cleared.json, {'interests': []})
        too_many = worker.post('/me/interests', data={'csrf': csrf, 'tags': [str(i) for i in range(9)]}, headers={'Accept': 'application/json'})
        self.assertEqual(too_many.status_code, 400)
        self.assertIn('最多 8 个方向', too_many.json['error'])
        # 方向条一直都在，不只给新人看
        self.post(worker, '/me/interests', {'tags': '图论'})
        self.assertIn('今天想往哪儿使劲', worker.get('/').text)

    def test_times_follow_each_viewers_own_time_zone(self):
        moment = datetime.now(timezone.utc) + timedelta(days=3)
        new_york = moment.astimezone(ZoneInfo('America/New_York'))
        owner = self.clients[0]
        owner.set_cookie('tz', 'America/New_York')
        self.post(owner, '/tasks/new', {**self.data, 'tags': '文档', 'title': '纽约时间截止',
                                         'deadline': new_york.replace(tzinfo=None).isoformat(timespec='minutes')})
        with connect(self.path) as db:
            stored = db.execute("SELECT deadline FROM tasks WHERE title='纽约时间截止'").fetchone()[0]
            task_id = db.execute("SELECT id FROM tasks WHERE title='纽约时间截止'").fetchone()[0]
        self.assertLess(abs((datetime.fromisoformat(stored) - moment).total_seconds()), 61)
        worker = self.clients[1]
        worker.set_cookie('tz', 'Asia/Tokyo')
        tokyo = moment.astimezone(ZoneInfo('Asia/Tokyo'))
        self.assertIn(f'{tokyo:%m/%d %H:%M}', worker.get(f'/tasks/{task_id}').text)
        self.assertIn(f'{new_york:%m/%d %H:%M}', owner.get(f'/tasks/{task_id}').text)
        self.assertIn('data-tz="Asia/Tokyo"', worker.get('/').text)
        # 不认识的时区退回团队时区，也不会出错
        worker.set_cookie('tz', '../../etc/passwd')
        self.assertIn('data-tz=""', worker.get('/').text)
        with connect(self.path) as db:
            for zone_name in ('Pacific/Kiritimati', 'Pacific/Pago_Pago'):
                week = discover.week_summary(db, ZoneInfo(zone_name))
                self.assertEqual(week['today'], datetime.now(ZoneInfo(zone_name)).weekday())

    def test_medal_case_lists_counts_history_and_where_to_get_more(self):
        self.finish(self.task_id)
        second = create_task(self.path, 1, {**self.data, 'title': '第二份文档'})
        self.finish(second, body='写得很清楚')
        create_task(self.path, 1, {**self.data, 'title': '一个加急的大任务', 'importance': 'major', 'urgency': 'urgent'})
        page = self.clients[1].get('/honors').text
        self.assertIn('data-count="2"', page)
        self.assertIn('class="tile locked" data-collection-key="major-urgent"', page)
        self.assertIn('1 个任务能拿', page)
        case = json.loads(page.split('<script type="application/json" id="case-data">')[1].split('</script>')[0])
        self.assertEqual(case['standard-normal']['count'], 2)
        self.assertEqual(case['standard-normal']['back']['quote'], '写得很清楚')
        self.assertEqual([item['title'] for item in case['standard-normal']['history']], ['第二份文档', '入门文档'])
        self.assertEqual(case['major-urgent']['can_get'], 1)
        self.assertIsNone(case['major-urgent']['back'])
        self.assertIn('class="inspect"', page)
        self.assertIn('Lv.', self.clients[1].get('/').text)
        self.assertIn('mini-case', self.clients[1].get('/').text)


if __name__ == '__main__':
    unittest.main()
