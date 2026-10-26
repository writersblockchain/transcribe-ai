import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import storage
from app import app, jobs, auth_attempts

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dbpatch=patch.object(storage,'DB_PATH',Path(self.tmp.name)/'cadence.sqlite3')
        self.dbpatch.start()
        jobs.clear();auth_attempts.clear()
        self.client=TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.dbpatch.stop();self.tmp.cleanup()

    def register(self, client, email='one@example.com'):
        r=client.post('/api/auth/register',json={'email':email,'password':'a-long-password'})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()

    def test_private_library_and_ownership(self):
        one=self.register(self.client)
        storage.save({'id':'secret','status':'completed','title':'Private','utterances':[]},one['id'])
        self.assertEqual(len(self.client.get('/api/transcripts').json()),1)
        with TestClient(app) as other:
            self.assertEqual(other.get('/api/transcripts').status_code,401)
            self.register(other,'two@example.com')
            self.assertEqual(other.get('/api/transcripts').json(),[])
            self.assertEqual(other.get('/api/transcripts/secret').status_code,404)
            self.assertEqual(other.patch('/api/transcripts/secret',json={'title':'attack','names':{}}).status_code,404)
            self.assertEqual(other.post('/api/transcripts',json={'url':'bad'}).status_code,400)
        self.assertEqual(self.client.get('/api/transcripts/secret').json()['title'],'Private')

    def test_saved_edits_survive_restart_and_login(self):
        one=self.register(self.client)
        storage.save({'id':'saved','status':'completed','utterances':[{'speaker':'A','start':0,'end':1,'text':'hello'}]},one['id'])
        r=self.client.patch('/api/transcripts/saved',json={'title':'My podcast','names':{'A':'Alice'},'url':'https://youtu.be/abcdefghijk'})
        self.assertEqual(r.status_code,200)
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/transcripts/saved').status_code,401)
        jobs.clear();storage.initialize()
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'one@example.com','password':'wrong-password'}).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'one@example.com','password':'a-long-password'}).status_code,200)
        saved=self.client.get('/api/transcripts/saved').json()
        self.assertEqual(saved['names'],{'A':'Alice'})
        self.assertEqual(saved['title'],'My podcast')
        self.assertEqual(saved['url'],'https://www.youtube.com/watch?v=abcdefghijk')

    def test_recovery_claimed_once_and_not_overwritten(self):
        folder=Path(self.tmp.name)/'recovery';folder.mkdir()
        (folder/'old.json').write_text(json.dumps({'id':'old','status':'completed','utterances':[{'speaker':'B','start':1,'end':2,'text':'preserved'}]}))
        storage.initialize()
        one=self.register(self.client)
        saved=self.client.get('/api/transcripts/recovered-old').json()
        self.assertEqual(saved['utterances'][0]['text'],'preserved')
        self.client.patch('/api/transcripts/recovered-old',json={'title':'Renamed','names':{'B':'Bob'}})
        storage.initialize()
        self.assertEqual(self.client.get('/api/transcripts/recovered-old').json()['title'],'Renamed')
        with TestClient(app) as other:
            self.register(other,'two@example.com')
            self.assertEqual(other.get('/api/transcripts').json(),[])

    def test_cross_origin_rejected_and_session_revoked(self):
        self.assertEqual(self.client.post('/api/auth/register',headers={'origin':'https://evil.example'},json={'email':'a@b.com','password':'long-password'}).status_code,403)
        self.register(self.client)
        token=self.client.cookies.get('cadence_session')
        self.client.post('/api/auth/logout')
        self.client.cookies.set('cadence_session',token)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)

    def test_expired_session_and_interrupted_job(self):
        one=self.register(self.client)
        storage.save({'id':'pending','status':'transcribing'},one['id'])
        storage.initialize()
        self.assertEqual(storage.get('pending',one['id'])['status'],'error')
        with storage.database() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)

    def test_validation_duplicate_password_hash(self):
        self.assertEqual(self.client.post('/api/auth/register',json={'email':'bad','password':'short'}).status_code,422)
        self.register(self.client)
        self.assertEqual(self.client.post('/api/auth/register',json={'email':'ONE@example.com','password':'a-long-password'}).status_code,409)
        with storage.database() as db:
            row=db.execute('SELECT password FROM users').fetchone()
            self.assertNotIn('a-long-password',row['password'])
        storage.save({'id':'saved','status':'completed','utterances':[]},self.client.get('/api/auth/me').json()['id'])
        self.assertEqual(self.client.patch('/api/transcripts/saved',json={'title':'title','names':{},'url':'https://evil.example'}).status_code,400)

if __name__=='__main__':unittest.main()
