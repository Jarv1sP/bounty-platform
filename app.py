import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from bounty.db import connect, initialize
from bounty.honors import IMPORTANCE, URGENCY, MEDALS, medal_key
from bounty.service import CATEGORIES, STATUSES, KINDS, InvalidAction, act, create_task, now, required


def create_app(config=None):
    settings = dict(config or {})
    default_data = Path(__file__).resolve().parent / 'instance'
    data_dir = Path(settings.get('DATA_DIR') or os.environ.get('BOUNTY_DATA_DIR') or
                    (Path(settings['DATABASE']).parent if settings.get('DATABASE') else default_data)).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, instance_path=str(data_dir), instance_relative_config=True)
    app.config.update(DATABASE=str(data_dir / 'bounty.sqlite3'), DATA_DIR=str(data_dir),
                      MAX_CONTENT_LENGTH=128 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax')
    app.config.update(settings)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        secret_path = Path(app.instance_path) / 'secret.key'
        try:
            with secret_path.open('x') as handle:
                os.chmod(secret_path, 0o600)
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = secret_path.read_text()
    initialize(app.config['DATABASE'])

    @app.before_request
    def load_user():
        g.user = None
        if session.get('user_id'):
            with connect(app.config['DATABASE']) as db:
                g.user = db.execute('SELECT id,name FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'].encode('utf-8'), request.form.get('csrf', '').encode('utf-8')):
            abort(400, description='表单已过期，请刷新后重试。')

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('auth', mode='login'))
            return view(*args, **kwargs)
        return wrapped

    @app.context_processor
    def context():
        return dict(categories=CATEGORIES, statuses=STATUSES, kinds=KINDS, current_time=now(),
                    importance_labels=IMPORTANCE, urgency_labels=URGENCY, medals=MEDALS, medal_key=medal_key)

    @app.template_filter('date')
    def date(value):
        return value[:16].replace('T', ' ') + ' UTC'

    @app.route('/auth/<mode>', methods=['GET', 'POST'])
    def auth(mode):
        if mode not in ('login', 'register'):
            abort(404)
        if request.method == 'POST':
            try:
                name = required(request.form, 'name', '用户名', 40)
                password = request.form.get('password', '')
                if not 8 <= len(password) <= 128:
                    raise InvalidAction('密码长度须为 8–128 个字符。')
                with connect(app.config['DATABASE'], write=True) as db:
                    if mode == 'register':
                        try:
                            user_id = db.execute('INSERT INTO users (name,password) VALUES (?,?)', (name, generate_password_hash(password))).lastrowid
                        except sqlite3.IntegrityError:
                            raise InvalidAction('用户名已被使用。')
                    else:
                        user = db.execute('SELECT * FROM users WHERE name=?', (name,)).fetchone()
                        if not user or not check_password_hash(user['password'], password):
                            raise InvalidAction('用户名或密码不正确。')
                        user_id = user['id']
                session.clear()
                session['user_id'] = user_id
                return redirect(url_for('index'))
            except InvalidAction as error:
                flash(str(error), 'error')
        return render_template('auth.html', mode=mode)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('index'))

    @app.get('/')
    @login_required
    def index():
        scope = request.args.get('scope', 'all')
        category, status, query = (request.args.get(k, '') for k in ('category', 'status', 'q'))
        clauses, params = [], []
        if scope in ('published', 'claimed'):
            clauses.append('t.owner_id=?' if scope == 'published' else 't.assignee_id=?')
            params.append(g.user['id'])
        if category in CATEGORIES:
            clauses.append('t.category=?'); params.append(category)
        if status in STATUSES:
            clauses.append('t.status=?'); params.append(status)
        if query:
            clauses.append('(t.title LIKE ? OR t.description LIKE ?)'); params.extend([f'%{query}%'] * 2)
        with connect(app.config['DATABASE']) as db:
            tasks = db.execute('SELECT t.*,u.name owner_name FROM tasks t JOIN users u ON u.id=t.owner_id' + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY t.id DESC', params).fetchall()
            counts = {row['status']: row['n'] for row in db.execute('SELECT status,COUNT(*) n FROM tasks GROUP BY status')}
            my_honors = db.execute('SELECT medal_key FROM honors WHERE user_id=?', (g.user['id'],)).fetchall()
            earned_keys = {row['medal_key'] for row in my_honors}
            featured = [row['medal_key'] for row in db.execute(
                'SELECT medal_key FROM featured_honors WHERE user_id=? ORDER BY slot', (g.user['id'],))]
        return render_template('index.html', tasks=tasks, scope=scope, category=category, status=status, query=query, counts=counts,
                               earned_keys=earned_keys, honor_total=len(my_honors),
                               medal_preview=featured or list(dict.fromkeys([*sorted(earned_keys), *MEDALS]))[:3])

    @app.route('/tasks/new', methods=['GET', 'POST'])
    @login_required
    def new_task():
        if request.method == 'POST':
            try:
                task_id = create_task(app.config['DATABASE'], g.user['id'], request.form)
                flash('任务已发布。', 'success')
                return redirect(url_for('detail', task_id=task_id))
            except InvalidAction as error:
                flash(str(error), 'error')
        return render_template('new.html')

    @app.get('/honors')
    @login_required
    def honors():
        with connect(app.config['DATABASE']) as db:
            awards = db.execute('''SELECT h.*,t.title,u.name owner_name FROM honors h
                JOIN tasks t ON t.id=h.task_id JOIN users u ON u.id=t.owner_id
                WHERE h.user_id=? ORDER BY h.awarded_at DESC,h.task_id DESC''', (g.user['id'],)).fetchall()
            featured = [row['medal_key'] for row in db.execute(
                'SELECT medal_key FROM featured_honors WHERE user_id=? ORDER BY slot', (g.user['id'],))]
        counts = {key: sum(a['medal_key'] == key for a in awards) for key in MEDALS}
        return render_template('honors.html', awards=awards, medal_counts=counts, featured=featured)

    @app.post('/honors/featured')
    @login_required
    def feature_honors():
        keys = list(dict.fromkeys(request.form.getlist('medals')))
        try:
            if len(keys) > 3 or any(key not in MEDALS for key in keys):
                raise InvalidAction('最多展示三种已获得的勋章。')
            with connect(app.config['DATABASE'], write=True) as db:
                earned = {row['medal_key'] for row in db.execute(
                    'SELECT medal_key FROM honors WHERE user_id=?', (g.user['id'],))}
                if any(key not in earned for key in keys):
                    raise InvalidAction('只能展示自己已获得的勋章。')
                db.execute('DELETE FROM featured_honors WHERE user_id=?', (g.user['id'],))
                db.executemany('INSERT INTO featured_honors (user_id,slot,medal_key) VALUES (?,?,?)',
                               [(g.user['id'], i + 1, key) for i, key in enumerate(keys)])
            flash('展示位已保存。', 'success')
        except InvalidAction as error:
            flash(str(error), 'error')
        return redirect(url_for('honors'))

    @app.post('/honors/reveal')
    @login_required
    def reveal_honors():
        # Read and mark in one transaction: refreshing or opening two tabs cannot replay a batch.
        with connect(app.config['DATABASE'], write=True) as db:
            awards = db.execute("""SELECT h.task_id,h.medal_key,t.title FROM honors h
                JOIN tasks t ON t.id=h.task_id WHERE h.user_id=? AND h.seen_at IS NULL
                ORDER BY h.awarded_at,h.task_id LIMIT 12""", (g.user['id'],)).fetchall()
            db.executemany('UPDATE honors SET seen_at=? WHERE task_id=? AND user_id=?',
                           [(now(), row['task_id'], g.user['id']) for row in awards])
        return jsonify(awards=[dict(row) for row in awards])

    @app.get('/tasks/<int:task_id>')
    @login_required
    def detail(task_id):
        with connect(app.config['DATABASE']) as db:
            task = db.execute('''SELECT t.*,u.name owner_name,a.name assignee_name FROM tasks t
                JOIN users u ON u.id=t.owner_id LEFT JOIN users a ON a.id=t.assignee_id WHERE t.id=?''', (task_id,)).fetchone()
            if not task:
                abort(404)
            events = db.execute('SELECT e.*,u.name FROM events e JOIN users u ON u.id=e.user_id WHERE task_id=? ORDER BY e.id', (task_id,)).fetchall()
            award = db.execute('SELECT * FROM honors WHERE task_id=?', (task_id,)).fetchone()
        feedback = session.pop('task_feedback', None)
        if feedback and feedback['task_id'] != task_id:
            feedback = None
        return render_template('detail.html', task=task, events=events, award=award, feedback=feedback)

    @app.post('/tasks/<int:task_id>/<action>')
    @login_required
    def task_action(task_id, action):
        try:
            act(app.config['DATABASE'], task_id, g.user['id'], action, request.form.get('body', ''))
            if action in ('claim', 'submit', 'accept', 'return'):
                session['task_feedback'] = {'task_id': task_id, 'action': action}
            flash('验收通过，勋章已授予认领人。' if action == 'accept' else '操作已保存。', 'success')
        except InvalidAction as error:
            flash(str(error), 'error')
        return redirect(url_for('detail', task_id=task_id))

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        return render_template('error.html', error=error), error.code

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', '5080')), debug=False)
