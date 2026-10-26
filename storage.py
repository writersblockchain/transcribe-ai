"""SQLite persistence and local account/session management."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv('CADENCE_DB', str(Path(__file__).parent / 'data' / 'cadence.sqlite3')))

@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with database() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), created REAL NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS conversations_owner ON conversations(user_id, created);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        # A stopped local worker cannot continue its download/polling task.
        for row in db.execute('SELECT id,data FROM conversations').fetchall():
            data = json.loads(row['data'])
            if data['status'] not in ('completed', 'error'):
                data.update(status='error', error='Processing was interrupted by a server restart. Please submit again. No partial transcript was saved.')
                db.execute('UPDATE conversations SET data=? WHERE id=?', (json.dumps(data), row['id']))
        owner = db.execute("SELECT value FROM settings WHERE key='recovery_owner'").fetchone()
        for path in (DB_PATH.parent / 'recovery').glob('*.json'):
            recovered = json.loads(path.read_text())
            if recovered.get('status') != 'completed':
                continue
            data = {'id': 'recovered-' + recovered['id'], 'url':'', 'title':'Recovered conversation',
                    'status':'completed', 'names':{}, 'recovered':True,
                    'utterances': [{ 'speaker':u.get('speaker') or 'Unknown', 'start':u['start'], 'end':u['end'], 'text':u['text']} for u in recovered.get('utterances') or []]}
            if not data['utterances'] and recovered.get('text'):
                data['utterances'] = [{'speaker':'Unknown','start':0,'end':0,'text':recovered['text']}]
            db.execute('INSERT OR IGNORE INTO conversations VALUES (?,?,?,?)', (data['id'], owner['value'] if owner else None, time.time(), json.dumps(data)))
    os.chmod(DB_PATH, 0o600)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def register(email, password):
    user_id = secrets.token_hex(16)
    encoded = password_hash(password)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO users VALUES (?,?,?)', (user_id, email, encoded))
        owner = db.execute("SELECT value FROM settings WHERE key='recovery_owner'").fetchone()
        if not owner:
            db.execute("INSERT INTO settings VALUES ('recovery_owner',?)", (user_id,))
            db.execute('UPDATE conversations SET user_id=? WHERE user_id IS NULL', (user_id,))
    return {'id':user_id, 'email':email}


def authenticate(email, password):
    with database() as db:
        row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    encoded = row['password'] if row else password_hash('dummy-password')
    valid = hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)
    return {'id':row['id'], 'email':row['email']} if row and valid else None


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session(user_id):
    token = secrets.token_urlsafe(32)
    with database() as db:
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (token_hash(token), user_id, time.time()+604800))
    return token


def session_user(token):
    if not token:
        return None
    with database() as db:
        row = db.execute('SELECT users.id, users.email FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?', (token_hash(token),time.time())).fetchone()
    return dict(row) if row else None


def logout(token):
    with database() as db:
        db.execute('DELETE FROM sessions WHERE token=?', (token_hash(token),))


def save(data, user_id):
    with database() as db:
        db.execute('INSERT INTO conversations VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (data['id'],user_id,time.time(),json.dumps(data)))


def get(job_id, user_id):
    with database() as db:
        row = db.execute('SELECT data FROM conversations WHERE id=? AND user_id=?', (job_id,user_id)).fetchone()
    return json.loads(row['data']) if row else None


def history(user_id):
    with database() as db:
        rows = db.execute('SELECT data,created FROM conversations WHERE user_id=? ORDER BY created DESC', (user_id,)).fetchall()
    return [{k:v for k,v in dict(json.loads(row['data']),created=row['created']).items() if k not in ('utterances','names','owner')} for row in rows]
