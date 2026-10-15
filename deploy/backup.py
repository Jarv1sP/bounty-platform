"""Online SQLite backup plus session secret. Run as root on the VPS; retain 30 daily copies."""
import argparse
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/opt/bounty-platform'))
    args = parser.parse_args()
    os.umask(0o077)
    root = args.root
    target = root / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target.mkdir(parents=True)
    source = sqlite3.connect((root / 'data/bounty.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)
    dest = sqlite3.connect(target / 'bounty.sqlite3')
    try:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
    finally:
        source.close()
        dest.close()
    shutil.copy2(root / 'data/secret.key', target / 'secret.key')
    for old in sorted((root / 'backups').iterdir(), reverse=True)[30:]:
        if old.is_dir() and len(old.name) == 22 and old.name.endswith('Z'):
            shutil.rmtree(old)
    print(target)


if __name__ == '__main__':
    main()
