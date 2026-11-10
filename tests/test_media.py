import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from media import download_audio, public_media_url, provider_json

class MediaTests(unittest.TestCase):
    def response(self, data=None, status=200, chunks=None, headers=None):
        r=Mock(status_code=status,headers=headers or {'Content-Type':'audio/mp4'},json=lambda:data)
        r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
        r.iter_content=Mock(return_value=iter(chunks or [b'audio']))
        return r

    def test_audio_download_does_not_forward_key(self):
        responses=[self.response({'ok':True,'data':{'durationSeconds':310,'formats':[{'id':'a-m4a','hasAudio':True,'hasVideo':False}]}}),self.response({'ok':True,'url':'https://cdn.example/audio'}),self.response()]
        with tempfile.TemporaryDirectory() as folder, patch('media.requests.get',side_effect=responses) as get, patch('media.public_media_url'):
            path=download_audio('https://youtube.com/watch?v=abcdefghijk','secret',Path(folder)/'audio')
            self.assertEqual(path.read_bytes(),b'audio')
        self.assertEqual(get.call_args_list[0].kwargs['headers'],{'x-api-key':'secret'})
        self.assertNotIn('headers',get.call_args_list[2].kwargs)

    def test_provider_limit_has_specific_error(self):
        with patch('media.requests.get',return_value=self.response(status=429)):
            with self.assertRaisesRegex(ValueError,'daily limit'):provider_json('/info','url','secret')

    def test_reject_long_video_before_spending_download_credit(self):
        info={'ok':True,'data':{'durationSeconds':7201}}
        with tempfile.TemporaryDirectory() as folder, patch('media.requests.get',return_value=self.response(info)) as get:
            with self.assertRaisesRegex(ValueError,'two hours'):download_audio('url','secret',Path(folder)/'audio')
            self.assertEqual(get.call_count,1)

    def test_private_url_rejected(self):
        with patch('media.socket.getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'invalid download'):public_media_url('https://localhost/audio')
        for url in ('http://example.com/audio','https://user:secret@example.com/audio','file:///etc/passwd'):
            with self.assertRaises(ValueError):public_media_url(url)

    def test_size_limit_enforced_during_stream(self):
        info={'data':{'durationSeconds':1,'formats':[{'id':'a-m4a','hasAudio':True,'hasVideo':False}]}}
        with tempfile.TemporaryDirectory() as folder, patch('media.provider_json',side_effect=[info,{'url':'https://cdn.example/audio'}]), patch('media.public_media_url'), patch('media.MAX_BYTES',2), patch('media.requests.get',return_value=self.response(chunks=[b'large'])):
            with self.assertRaisesRegex(ValueError,'200 MB'):download_audio('url','secret',Path(folder)/'audio')

if __name__=='__main__':unittest.main()
