"""Shared SQLite/libSQL data layer and role-scoped HTTP API."""
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
COOKIE = 'greenloop_session'
SESSION_AGE = 12 * 3600
WORK = {'requested', 'assigned', 'arrived'}
ROLES = {'resident', 'crew', 'coordinator'}
LOG = logging.getLogger('greenloop')


class Database:
    def __init__(self, path=None, *, remote=False):
        self.path = Path(path or os.getenv('GREENLOOP_DB') or ROOT / 'runtime' / 'greenloop.sqlite3')
        self.url = os.getenv('TURSO_DATABASE_URL', '') if remote else ''
        self.token = os.getenv('TURSO_AUTH_TOKEN', '') if remote else ''
        if remote:
            self.url = self.url.replace('libsql://', 'https://', 1).rstrip('/')
            target = urlsplit(self.url)
            if target.scheme != 'https' or not target.hostname or target.username or target.password or target.query or target.fragment or not self.token:
                raise RuntimeError('Configure TURSO_DATABASE_URL and TURSO_AUTH_TOKEN')

    def sql(self, statement, *args):
        if not self.url:
            with sqlite3.connect(self.path, timeout=8) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute('PRAGMA foreign_keys=ON')
                rows = [dict(row) for row in conn.execute(statement, args)]
            return rows
        def encode(value):
            if value is None:
                return {'type': 'null'}
            if isinstance(value, int):
                return {'type': 'integer', 'value': str(value)}
            if isinstance(value, float):
                return {'type': 'float', 'value': value}
            return {'type': 'text', 'value': value}
        payload = {'requests': [{'type': 'execute', 'stmt': {
            'sql': statement, 'args': [encode(v) for v in args], 'want_rows': True}}, {'type': 'close'}]}
        req = Request(self.url + '/v2/pipeline', data=json.dumps(payload).encode(), headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=10) as response:
            result = json.load(response)['results'][0]
        if result['type'] != 'ok':
            raise RuntimeError('Database statement failed')
        result = result['response']['result']
        def decode(cell):
            kind, value = cell['type'], cell.get('value')
            return int(value) if kind == 'integer' else float(value) if kind == 'float' else value
        names = [col['name'] for col in result['cols']]
        return [dict(zip(names, map(decode, row))) for row in result['rows']]

    def setup(self):
        if not self.url:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        for statement in (ROOT / 'schema.sql').read_text().split(';'):
            if statement.strip():
                self.sql(statement)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def create_account(db, role, email, name, password):
    email = email.strip().lower()
    name = name.strip()
    if role not in ROLES or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        raise ValueError('Provide a valid role and email.')
    if not 1 <= len(name) <= 80 or not 12 <= len(password) <= 128:
        raise ValueError('Name must be 1–80 characters and password 12–128 characters.')
    db.sql('INSERT INTO accounts(id,email,name,role,password) VALUES(?,?,?,?,?)',
           secrets.token_hex(16), email, name, role, password_hash(password))


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def one(rows):
    return rows[0] if rows else None


def session_token(cookie):
    jar = SimpleCookie()
    try:
        jar.load(cookie or '')
    except CookieError:
        return ''
    item = jar.get(COOKIE)
    return item.value if item and re.fullmatch(r'[a-f0-9]{64}', item.value) else ''


def view_user(row):
    return {k: row[k] for k in ('id', 'name', 'email', 'role')}


class Service:
    def __init__(self, db):
        self.db = db

    def handle(self, method, path, data, cookie='', secure=False):
        q = self.db.sql
        now = int(time.time())
        token = session_token(cookie)
        flags = '; Path=/; HttpOnly; SameSite=Strict' + ('; Secure' if secure else '')
        if method == 'POST' and path == '/api/login':
            email, password, portal = data.get('email'), data.get('password'), data.get('portal')
            if not isinstance(email, str) or not isinstance(password, str) or len(password) > 128 or len(email) > 254:
                raise APIError(400, 'Check your email and password.')
            account = one(q('SELECT * FROM accounts WHERE email=?', email.strip().lower()))
            if account and account['locked_until'] > now:
                raise APIError(429, 'Too many attempts. Try again in a few minutes.')
            stored = account['password'] if account else '0'*32 + ':' + '0'*128
            valid = hmac.compare_digest(password_hash(password, stored.split(':',1)[0]), stored)
            if not account or not valid:
                if account:
                    q('UPDATE accounts SET failures=CASE WHEN failures>=4 THEN 0 ELSE failures+1 END, locked_until=CASE WHEN failures>=4 THEN ? ELSE locked_until END WHERE id=?', now+300, account['id'])
                raise APIError(401, 'Email or password is incorrect.')
            if portal not in ('resident', 'collection') or (account['role'] == 'resident') != (portal == 'resident'):
                raise APIError(403, 'Use the sign-in page for your role.')
            q('UPDATE accounts SET failures=0, locked_until=0 WHERE id=?', account['id'])
            q('DELETE FROM sessions WHERE expires<=?', now)
            if token:
                q('DELETE FROM sessions WHERE digest=?', digest(token))
            token = secrets.token_hex(32)
            q('INSERT INTO sessions VALUES (?,?,?)', digest(token), account['id'], now+SESSION_AGE)
            return {'user': view_user(account)}, f'{COOKIE}={token}; Max-Age={SESSION_AGE}' + flags
        if method == 'POST' and path == '/api/logout':
            if token:
                q('DELETE FROM sessions WHERE digest=?', digest(token))
            return {'ok': True}, f'{COOKIE}=; Max-Age=0' + flags
        user = one(q('SELECT a.id,a.name,a.email,a.role FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.digest=? AND s.expires>?', digest(token), now)) if token else None
        if not user:
            raise APIError(401, 'Sign in to continue.')
        uid, role = user['id'], user['role']
        if method == 'GET' and path == '/api/state':
            if role == 'resident':
                return {'user': user, 'location': one(q('SELECT * FROM locations WHERE resident_id=?', uid)),
                        'pickups': q('SELECT * FROM pickups WHERE resident_id=? ORDER BY status IN (\'requested\',\'assigned\',\'arrived\') DESC, created DESC, rowid DESC LIMIT 50', uid)}, None
            base = "SELECT p.*,r.name AS resident,c.name AS crew FROM pickups p JOIN accounts r ON p.resident_id=r.id LEFT JOIN accounts c ON p.assigned_to=c.id"
            scope, params = ('', ()) if role == 'coordinator' else (' WHERE p.assigned_to=?', (uid,))
            return {'user': user, 'pickups': q(base + scope + " ORDER BY p.status IN ('requested','assigned','arrived') DESC, p.created DESC,p.rowid DESC LIMIT 300", *params),
                    'crew': q("SELECT id,name FROM accounts WHERE role='crew' ORDER BY name,id") if role == 'coordinator' else []}, None
        if method != 'POST':
            raise APIError(404, 'Page not found.')
        if path == '/api/location':
            self.require(role, 'resident')
            point, unit, note = (self.field(data, key, limit, required) for key,limit,required in (
                ('point',80,True),('unit',40,True),('note',160,False)))
            try:
                lat, lon = float(data['lat']), float(data['lon'])
                if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
                    raise ValueError()
            except (KeyError, ValueError, TypeError, OverflowError):
                raise APIError(400, 'Set a valid pickup pin or enter coordinates.')
            q('INSERT INTO locations VALUES (?,?,?,?,?,?) ON CONFLICT(resident_id) DO UPDATE SET point=excluded.point,unit=excluded.unit,note=excluded.note,lat=excluded.lat,lon=excluded.lon', uid,point,unit,note,round(lat,6),round(lon,6))
        elif path == '/api/request':
            self.require(role, 'resident')
            rows = q("INSERT OR IGNORE INTO pickups(id,resident_id,status,point,unit,note,lat,lon,created,updated) SELECT ?,resident_id,'requested',point,unit,note,lat,lon,?,? FROM locations WHERE resident_id=? RETURNING id", secrets.token_hex(16),now,now,uid)
            if not rows and not one(q("SELECT id FROM pickups WHERE resident_id=? AND status IN ('requested','assigned','arrived')", uid)):
                raise APIError(409, 'Save a pickup point first.')
        elif path in ('/api/cancel','/api/assign','/api/status'):
            pickup = self.field(data, 'id', 32, True)
            if path == '/api/cancel':
                self.require(role, 'resident')
                rows = q("UPDATE pickups SET status='cancelled',updated=? WHERE id=? AND resident_id=? AND status='requested' RETURNING id", now,pickup,uid)
            elif path == '/api/assign':
                self.require(role, 'coordinator')
                crew = self.field(data,'crew',32,True)
                rows = q("UPDATE pickups SET status='assigned',assigned_to=?,updated=? WHERE id=? AND status IN ('requested','assigned') AND EXISTS(SELECT 1 FROM accounts WHERE id=? AND role='crew') RETURNING id",crew,now,pickup,crew)
            else:
                self.require(role, 'crew')
                target = self.field(data,'status',16,True)
                source = {'arrived':'assigned','collected':'arrived','unavailable':'arrived'}.get(target)
                if not source:
                    raise APIError(400, 'Invalid pickup status.')
                reason = self.field(data,'reason',120,True) if target == 'unavailable' else ''
                scope, args = (' AND assigned_to=?',(uid,)) if role == 'crew' else ('',())
                rows = q("UPDATE pickups SET status=?,reason=?,updated=? WHERE id=? AND status=?" + scope + ' RETURNING id',target,reason,now,pickup,source,*args)
            if not rows:
                raise APIError(409, 'This action is no longer available. Refresh and try again.')
        else:
            raise APIError(404, 'Page not found.')
        return {'ok': True}, None

    @staticmethod
    def field(data, name, limit, required):
        value = data.get(name, '')
        if not isinstance(value,str) or len(value.strip()) > limit or (required and not value.strip()):
            raise APIError(400, 'Check the ' + name + ' field.')
        return value.strip()

    @staticmethod
    def require(role, *allowed):
        if role not in allowed:
            raise APIError(403, 'Your role cannot perform this action.')
