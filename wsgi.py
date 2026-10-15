"""Cloud entrypoint. One trusted Caddy proxy; independent persistent SQLite data."""
import hashlib
import os
import time

from flask import request, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import SecurityError
from app import create_app
from bounty.db import connect


def create_cloud_app():
    domain = os.environ['BOUNTY_DOMAIN']
    invite = os.environ['BOUNTY_INVITE_CODE']
    if not domain or len(invite) < 16:
        raise RuntimeError('Set BOUNTY_DOMAIN and a random BOUNTY_INVITE_CODE of at least 16 characters.')
    app = create_app(dict(
        SHOW_DEMO_LOGIN=False, INVITE_CODE=invite,
        SESSION_COOKIE_NAME='__Host-bounty_session', SESSION_COOKIE_SECURE=True,
        TRUSTED_HOSTS=[domain, 'localhost', '127.0.0.1'],
    ))
    # The service has no public port: only Caddy can supply these headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    @app.errorhandler(SecurityError)
    def invalid_host(error):
        return 'Invalid host', 400

    with connect(app.config['DATABASE'], write=True) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS auth_windows (
            client TEXT NOT NULL, window INTEGER NOT NULL, attempts INTEGER NOT NULL,
            PRIMARY KEY(client,window))''')

    @app.before_request
    def throttle_auth():
        if request.method != 'POST' or request.endpoint != 'auth':
            return
        window = int(time.time()) // 60
        client = hashlib.sha256((request.remote_addr or '').encode()).hexdigest()
        with connect(app.config['DATABASE'], write=True) as db:
            db.execute('DELETE FROM auth_windows WHERE window<?', (window - 60,))
            db.execute('''INSERT INTO auth_windows VALUES (?,?,1)
                ON CONFLICT(client,window) DO UPDATE SET attempts=attempts+1''', (client, window))
            minute = db.execute('SELECT attempts FROM auth_windows WHERE client=? AND window=?',
                                (client, window)).fetchone()[0]
            hour = db.execute('SELECT SUM(attempts) FROM auth_windows WHERE client=?', (client,)).fetchone()[0]
        if minute > 30 or hour > 300:
            return render_template('auth.html', mode=request.view_args['mode'],
                                   rate_limited=True), 429, {'Retry-After': '60'}

    return app
