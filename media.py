"""Bounded audio retrieval via Yoinku. Credentials never go to download hosts."""
import ipaddress
import socket
import time
from urllib.parse import urlparse, urljoin
import requests

API = 'https://yoinku.com/api/v1'
MAX_BYTES = 200 * 1024 * 1024


def provider_json(endpoint, url, key, **params):
    try:
        response = requests.get(API + endpoint, params={'url': url, **params}, headers={'x-api-key': key}, timeout=(15,180), allow_redirects=False)
        if response.status_code == 429:
            raise ValueError('The audio download provider has reached its rate or daily limit. Please try later. The free plan allows five downloads per day across this app.')
        if response.status_code in (401,403):
            raise ValueError('The audio download provider rejected access. Please contact the app owner to check its configuration.')
        if response.status_code == 404:
            raise ValueError('The audio download provider could not find this public video.')
        if response.status_code != 200:
            raise ValueError('The audio download provider is temporarily unavailable. Please try again later.')
        data=response.json()
        if not isinstance(data,dict) or not data.get('ok'):
            raise ValueError('The audio download provider could not process this video.')
        return data
    except (requests.RequestException, requests.exceptions.JSONDecodeError) as exc:
        raise ValueError('The audio download provider could not be reached. Please try again later.') from None


def public_media_url(url):
    try:
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError()
        addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError()
    except (ValueError,OSError,TypeError):
        raise ValueError('The audio provider returned an invalid download address.') from None
    return url


def download_audio(url, key, destination):
    info=provider_json('/info',url,key).get('data',{})
    duration=info.get('durationSeconds')
    if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not 0<duration<=7200:
        raise ValueError('Choose a public, non-live video with a known duration of two hours or less.')
    formats=info.get('formats') or []
    audio=[f.get('id') for f in formats if f.get('hasAudio') and not f.get('hasVideo') and f.get('id')]
    if not audio:
        raise ValueError('The audio provider could not find an audio-only format for this video.')
    selected='a-m4a' if 'a-m4a' in audio else audio[0]
    media_url=provider_json('/download',url,key,format=selected).get('url')
    deadline=time.monotonic()+300
    try:
        for _ in range(4):
            public_media_url(media_url)
            # No x-api-key on this request or any redirect.
            with requests.get(media_url,stream=True,timeout=(15,60),allow_redirects=False) as response:
                if response.status_code in (301,302,303,307,308):
                    location=response.headers.get('Location')
                    if not location:break
                    media_url=urljoin(media_url,location)
                    continue
                response.raise_for_status()
                content_type=response.headers.get('Content-Type','').split(';')[0].lower()
                if not content_type.startswith(('audio/','video/','application/octet-stream')):
                    raise ValueError('The audio provider returned an unsupported file instead of audio.')
                length=response.headers.get('Content-Length')
                if length and int(length)>MAX_BYTES:
                    raise ValueError('This video’s audio exceeds the 200 MB limit.')
                size=0
                with destination.open('wb') as output:
                    for chunk in response.iter_content(1024*1024):
                        size+=len(chunk)
                        if size>MAX_BYTES:raise ValueError('This video’s audio exceeds the 200 MB limit.')
                        if time.monotonic()>deadline:raise ValueError('Audio download timed out. Please try again.')
                        output.write(chunk)
                if not size:raise ValueError('The audio provider returned an empty file.')
                return destination
        raise ValueError('The audio provider returned too many download redirects.')
    except requests.RequestException:
        raise ValueError('Could not retrieve the audio file from the download provider. Please try again.') from None
