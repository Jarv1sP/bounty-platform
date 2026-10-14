"""Build an offline, pure-Python local release with an independent demo database."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bounty.db import SCHEMA, connect
from bounty.demo import seed_demo

DEPENDENCIES = {
    'Flask': 'flask', 'Werkzeug': 'werkzeug', 'Jinja2': 'jinja2',
    'MarkupSafe': 'markupsafe', 'itsdangerous': 'itsdangerous',
    'click': 'click', 'blinker': 'blinker', 'colorama': 'colorama',
}


def build():
    dist = ROOT / 'dist'
    package = dist / 'bounty-platform-local'
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    files = ['app.py', 'run.py', 'manage.py', 'start.bat', 'start.sh', 'requirements.txt',
             'README.md', 'RELEASE_NOTES.txt']
    for name in files:
        shutil.copy2(ROOT / name, package / name)
    for name in ('bounty', 'templates', 'tests'):
        shutil.copytree(ROOT / name, package / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (package / 'static').mkdir()
    for name in ('style.css', 'ui.js', 'board.css', 'board.js'):
        shutil.copy2(ROOT / 'static' / name, package / 'static' / name)
    (package / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts' / 'check_motion.py', package / 'scripts' / 'check_motion.py')
    (package / 'database').mkdir()
    (package / 'database' / 'schema.sql').write_text('-- SQLite schema; see bounty/db.py for migrations.\n' + SCHEMA, encoding='utf-8')
    (package / 'START_HERE.txt').write_text(
        '搭把手 · 本地运行包\n\n'
        '1. 安装 Python 3.10+，完整解压 ZIP。\n'
        '2. Windows 双击 start.bat；macOS/Linux 执行 python3 run.py。\n'
        '3. 打开 http://127.0.0.1:5080 。\n\n'
        '演示用户：发布者 / 认领人 / 其他成员，密码均为 demo12345。\n'
        '已包含独立演示数据库与运行依赖；任务操作会真实保存。\n'
        '无需 Node/MySQL，无需联网安装依赖，不会公开上线。\n'
        '新建干净数据目录：python run.py --data-dir my-data\n'
        '详细操作和备份方法见 README.md。\n', encoding='utf-8-sig')
    vendor = package / 'vendor'
    vendor.mkdir()
    versions = {}
    notices = ['Bundled dependencies retain their upstream licenses in each *.dist-info directory.',
               'MarkupSafe uses its pure-Python fallback; native extension binaries are intentionally omitted.', '']
    for distribution, module in DEPENDENCIES.items():
        metadata = importlib.metadata.distribution(distribution)
        versions[distribution] = metadata.version
        source = Path(metadata.locate_file(module))
        shutil.copytree(source, vendor / module,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.so', '*.pyd', '*.dll', 'tests'))
        info = next(Path(item).parent for item in metadata.files if str(item).endswith('.dist-info/METADATA'))
        shutil.copytree(metadata.locate_file(info), vendor / info.name)
        notices.append(f'{distribution} {metadata.version}: {info.name}')
    (package / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices) + '\n', encoding='utf-8')
    (package / 'dependency-versions.json').write_text(json.dumps(versions, indent=2), encoding='utf-8')
    (package / 'instance').mkdir()
    database = package / 'instance' / 'bounty.sqlite3'
    seed_demo(database)
    with connect(database) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Demo database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Demo database foreign key check failed')
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    manifest = {str(path.relative_to(package)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(package.rglob('*')) if path.is_file()}
    (package / 'MANIFEST.sha256.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    archive = dist / 'bounty-platform-local-v1.0.0.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                zip_file.write(path, path.relative_to(dist))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest,
                      'files': len(manifest) + 1, 'dependencies': versions}, indent=2))


if __name__ == '__main__':
    build()
