"""Start a local Greenloop walkthrough with generated review accounts."""
import argparse
import json
import os
import secrets
import hashlib
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from greenloop import Database, ROOT, create_account
from manage import Local

ROLES = {'resident': 'Maya Rao', 'coordinator': 'Dispatch coordinator', 'crew': 'Collection crew'}


def review_accounts(db, credentials):
    if not credentials.exists():
        if db.sql('SELECT id FROM accounts LIMIT 1'):
            raise RuntimeError('This review database already has accounts. Restore its review-logins.json, or choose a fresh --data-dir.')
        rows = {role: {'email': role + '@greenloop.test', 'password': secrets.token_urlsafe(15)} for role in ROLES}
        fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(rows, file, indent=2)
    rows = json.loads(credentials.read_text(encoding='utf-8'))
    for role, name in ROLES.items():
        account = rows[role]
        existing = db.sql('SELECT role FROM accounts WHERE email=?', account['email'])
        if not existing:
            create_account(db, role, account['email'], name, account['password'])
        elif existing[0]['role'] != role:
            raise RuntimeError('Unexpected role for a review account.')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8775)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data-dir', type=lambda path: ROOT / path, default=ROOT / 'runtime' / 'quickstart')
    args = parser.parse_args()
    if sys.version_info < (3, 12) or not hasattr(hashlib, "scrypt"):
        parser.error("Use Python 3.12+ with OpenSSL (for example, the python.org installer).")
    try:
        with ThreadingHTTPServer(('127.0.0.1', args.port), Local) as server:
            db = Database(args.data_dir / 'greenloop.sqlite3')
            db.setup()
            accounts = review_accounts(db, args.data_dir / 'review-logins.json')
            Local.db = db
            url = f'http://127.0.0.1:{server.server_port}/'
            print(f'Greenloop: {url}\nLocal review accounts:', flush=True)
            for role, account in accounts.items():
                print(f'  {role:12} {account["email"]}  {account["password"]}', flush=True)
            print('Press Ctrl+C to stop.', flush=True)
            if not args.no_browser:
                browser = threading.Timer(0.3, webbrowser.open, args=(url,))
                browser.daemon = True
                browser.start()
            server.serve_forever()
    except KeyboardInterrupt:
        return
    except (OSError, RuntimeError) as error:
        parser.exit(1, f'{error}\nIf the port is busy, use --port 8776.\n')


if __name__ == '__main__':
    main()
