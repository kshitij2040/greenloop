"""Local server and account provisioning. Run python3 manage.py --help."""
import argparse
import getpass
import secrets
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from api.index import handler
from greenloop import Database, ROOT, create_account


class Local(handler, SimpleHTTPRequestHandler):
    secure = False
    db = None

    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'public'),**kwargs)

    def database(self):
        return self.db

    def do_GET(self):
        return self.run_api() if urlsplit(self.path).path.startswith('/api/') else SimpleHTTPRequestHandler.do_GET(self)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', help='Local SQLite file; default runtime/greenloop.sqlite3')
    parser.add_argument('--remote', action='store_true', help='Use Turso credentials from the environment')
    sub = parser.add_subparsers(dest='action',required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--port',type=int,default=8775)
    sub.add_parser('init')
    account = sub.add_parser('add-account')
    account.add_argument('role', choices=['resident','crew','coordinator'])
    account.add_argument('email')
    account.add_argument('name')
    sub.add_parser('sample',help='Create fictional review accounts in a fresh local database')
    args = parser.parse_args()
    if args.remote and args.action in ('sample','serve'):
        parser.error('Use a local database for sample and serve.')
    db = Database(args.db,remote=args.remote)
    if args.action == 'serve' and not db.path.exists():
        parser.error('Initialize the local database with init or sample before serving.')
    db.setup()
    if args.action == 'add-account':
        password = getpass.getpass('Password (at least 12 characters): ')
        if password != getpass.getpass('Confirm password: '):
            parser.error('Passwords do not match.')
        create_account(db,args.role,args.email,args.name,password)
        print('Account created.')
    elif args.action == 'sample':
        if db.sql('SELECT id FROM accounts LIMIT 1'):
            parser.error('Sample requires an empty database. Use --db runtime/review.sqlite3.')
        for role,name in [('resident','Maya Rao'),('crew','Collection crew'),('coordinator','Dispatch coordinator')]:
            email = role+'@greenloop.test'
            password = secrets.token_urlsafe(15)
            create_account(db,role,email,name,password)
            print(f'{role}: {email}  {password}')
    elif args.action == 'serve':
        Local.db = db
        with ThreadingHTTPServer(('127.0.0.1',args.port),Local) as server:
            print(f'Greenloop: http://127.0.0.1:{args.port}/',flush=True)
            server.serve_forever()
    else:
        print('Schema ready.')


if __name__ == '__main__':
    main()
