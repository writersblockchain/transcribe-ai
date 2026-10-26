import os
import tempfile
from pathlib import Path
import storage
import unittest
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from app import app, jobs, transcribe, youtube_url


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpatch = patch.object(storage, 'DB_PATH', Path(self.tmp.name)/'test.sqlite3')
        self.dbpatch.start()
        storage.initialize()
        from app import auth_attempts
        auth_attempts.clear()
        self.client = TestClient(app)
        self.user = self.client.post('/api/auth/register', json={'email':'test@example.com','password':'long-password'}).json()
        jobs.clear()

    def tearDown(self):
        self.dbpatch.stop()
        self.tmp.cleanup()

    def test_canonical_links(self):
        expected = 'https://www.youtube.com/watch?v=abcdefghijk'
        for url in ('https://youtu.be/abcdefghijk?t=30', expected + '&list=ignored',
                    'https://m.youtube.com/shorts/abcdefghijk'):
            self.assertEqual(youtube_url(url), expected)

    def test_reject_untrusted_hosts_and_nonvideos(self):
        for url in ('file:///etc/passwd', 'https://youtube.com.evil.test/watch?v=abcdefghijk',
                    'https://youtube.com@localhost/watch?v=abcdefghijk',
                    'https://youtube.com/playlist?list=abcdefghijk',
                    'https://youtube.com:9000/watch?v=abcdefghijk'):
            with self.assertRaises(ValueError):
                youtube_url(url)

    def test_missing_key_and_invalid_url(self):
        with patch.dict(os.environ, {'ASSEMBLYAI_API_KEY': ''}):
            self.assertEqual(self.client.post('/api/transcripts', json={'url':'https://youtu.be/abcdefghijk'}).status_code, 503)
            self.assertEqual(self.client.post('/api/transcripts', json={'url':'https://example.com'}).status_code, 400)

    def test_missing_job_and_static_page(self):
        self.assertEqual(self.client.get('/api/transcripts/missing').status_code, 404)
        self.assertIn('Every voice.', self.client.get('/').text)

    def test_concurrency_limit(self):
        jobs['active'] = {'status': 'transcribing'}
        with patch.dict(os.environ, {'ASSEMBLYAI_API_KEY': 'test'}):
            self.assertEqual(self.client.post('/api/transcripts', json={'url':'https://youtu.be/abcdefghijk'}).status_code, 429)

    def test_pipeline_preserves_speakers_and_timestamps(self):
        from pathlib import Path
        jobs['test'] = {'id':'test','status':'queued','owner':self.user['id']}
        def download(args, **kwargs):
            output = args[args.index('-o') + 1].replace('%(ext)s', 'm4a')
            Path(output).write_bytes(b'fake audio')
            return Mock(returncode=0)
        def response(data):
            return Mock(json=lambda: data, raise_for_status=lambda: None)
        utterance = {'speaker':'A', 'start':100, 'end':200, 'text':'Hello'}
        with patch('app.subprocess.run', side_effect=download), \
             patch('app.requests.post', side_effect=[response({'upload_url':'https://example.com/audio'}),response({'id':'remote'})]) as post, \
             patch('app.requests.get', return_value=response({'status':'completed','utterances':[utterance]})):
            transcribe('test', 'https://www.youtube.com/watch?v=abcdefghijk', 'test')
        self.assertTrue(post.call_args.kwargs['json']['speaker_labels'])
        self.assertEqual(jobs['test']['status'], 'completed')
        self.assertEqual(jobs['test']['utterances'], [utterance])

    def test_download_failure_is_visible(self):
        jobs['test'] = {'id':'test','status':'queued','owner':self.user['id']}
        with patch('app.subprocess.run', return_value=Mock(returncode=1)):
            transcribe('test', 'https://www.youtube.com/watch?v=abcdefghijk', 'test')
        self.assertEqual(jobs['test']['status'], 'error')
        self.assertIn('download', jobs['test']['error'])


if __name__ == '__main__':
    unittest.main()
