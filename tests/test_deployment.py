import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import storage
from app import app

class DeploymentTests(unittest.TestCase):
    def test_requires_persistent_volume_on_railway(self):
        with patch.dict(os.environ, {'RAILWAY_ENVIRONMENT_ID':'test','RAILWAY_VOLUME_MOUNT_PATH':''}):
            with self.assertRaisesRegex(RuntimeError, 'persistent volume'):
                with TestClient(app):
                    pass

    def test_health_and_explicit_frontend_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(storage, 'DB_PATH', Path(folder)/'db.sqlite3'), patch.dict(os.environ, {'RAILWAY_ENVIRONMENT_ID':'test','RAILWAY_VOLUME_MOUNT_PATH':folder,'APP_ORIGINS':'https://cadence.example'}):
                with TestClient(app) as client:
                    self.assertEqual(client.get('/api/health').json(), {'status':'ok'})
                    self.assertEqual(client.post('/api/auth/logout',headers={'Origin':'https://cadence.example','Sec-Fetch-Site':'cross-site'}).status_code,200)
                    self.assertEqual(client.post('/api/auth/logout',headers={'Origin':'https://attacker.example'}).status_code,403)

if __name__=='__main__':unittest.main()
