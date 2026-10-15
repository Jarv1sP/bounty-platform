"""Initialize, seed or back up the local SQLite database."""
import argparse
import getpass
import os
import sqlite3
import sys
from pathlib import Path
from run import ROOT
from bounty.db import initialize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('BOUNTY_DATA_DIR', ROOT / 'instance')))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create empty database tables')
    commands.add_parser('demo', help='Seed an empty database only')
    backup = commands.add_parser('backup', help='Consistent SQLite backup; refuses to overwrite')
    backup.add_argument('output', type=Path)
    admin = commands.add_parser('admin', help='Make a registered user an admin (maintains the team tag list)')
    admin.add_argument('name')
    admin.add_argument('--revoke', action='store_true', help='Take admin away instead')
    user = commands.add_parser('create-user', help='Create a separate local account; never copies GPUQ accounts')
    user.add_argument('name')
    user.add_argument('--admin', action='store_true')
    user.add_argument('--password-stdin', action='store_true')
    reset = commands.add_parser('reset-password', help='Operator-assisted account recovery')
    reset.add_argument('name')
    reset.add_argument('--password-stdin', action='store_true')
    args = parser.parse_args()
    data = args.data_dir.resolve()
    database = data / 'bounty.sqlite3'
    if args.command == 'backup':
        if not database.exists():
            parser.error('Database does not exist')
        output = args.output.resolve()
        if output.exists():
            parser.error('Backup output already exists; choose a new filename')
        output.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
        destination = sqlite3.connect(output)
        try:
            source.backup(destination)
        finally:
            source.close()
            destination.close()
        print(f'Backup: {output}')
    elif args.command in ('create-user', 'reset-password'):
        from werkzeug.security import generate_password_hash
        from bounty.db import connect
        password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('New password: ')
        if not 8 <= len(password) <= 128 or not 1 <= len(args.name.strip()) <= 40:
            parser.error('Name must be 1–40 characters and password 8–128 characters')
        data.mkdir(parents=True, exist_ok=True)
        initialize(database)
        with connect(database, write=True) as db:
            if args.command == 'create-user':
                try:
                    db.execute('INSERT INTO users (name,password,is_admin) VALUES (?,?,?)',
                               (args.name.strip(), generate_password_hash(password), int(args.admin)))
                except sqlite3.IntegrityError:
                    parser.error('Account already exists; no changes made')
            else:
                changed = db.execute('UPDATE users SET password=? WHERE name=?',
                                     (generate_password_hash(password), args.name.strip())).rowcount
                if not changed:
                    parser.error('Account not found')
        print('Account saved.')
    elif args.command == 'admin':
        if not database.exists():
            parser.error('Database does not exist')
        initialize(database)
        from bounty.service import InvalidAction
        from bounty.tags import grant
        try:
            grant(database, args.name, not args.revoke)
        except InvalidAction as error:
            parser.error(str(error))
        print(f'{args.name} {"不再是" if args.revoke else "现在是"}管理员。')
    else:
        data.mkdir(parents=True, exist_ok=True)
        initialize(database)
        if args.command == 'demo':
            from bounty.demo import seed_demo
            try:
                count = seed_demo(database)
            except ValueError as error:
                parser.error(str(error))
            print(f'Created {count} demo tasks. Password: demo12345')
        print(f'Database: {database}')


if __name__ == '__main__':
    main()
