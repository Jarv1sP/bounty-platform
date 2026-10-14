"""Local-only launcher. Bundled releases load pure-Python dependencies from vendor/."""
import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / 'vendor').is_dir():
    sys.path.insert(0, str(ROOT / 'vendor'))


def main():
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 or newer is required.')
    parser = argparse.ArgumentParser(description='Bounty platform (local only)')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Listen address; use 0.0.0.0 only on a trusted team network')
    parser.add_argument('--port', type=int, default=5080)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'instance')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    try:
        from app import create_app
        from werkzeug.serving import make_server
    except ImportError as error:
        raise SystemExit('Dependencies are missing. Run: python -m pip install -r requirements.txt') from error
    app = create_app({'DATA_DIR': str(args.data_dir.resolve())})
    local = args.host in ('127.0.0.1', 'localhost', '0.0.0.0', '::')
    url = f'http://127.0.0.1:{args.port}' if local else f'http://{args.host}:{args.port}'
    try:
        server = make_server(args.host, args.port, app, threaded=True)
    except (OSError, SystemExit):
        raise SystemExit(f'Cannot start on port {args.port}. Try: python run.py --port {args.port + 1}')
    print(f'\nBounty platform: {url}\nData: {app.config["DATABASE"]}\nPress Ctrl+C to stop.\n', flush=True)
    if args.host not in ('127.0.0.1', 'localhost'):
        print('Listening beyond this computer: anyone who can reach this address can open the sign-in page.\n', flush=True)
    if not args.no_browser:
        opener = threading.Timer(.4, lambda: webbrowser.open(url))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped. Data is saved.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
