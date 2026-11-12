"""Bounded downloads from fixed upstream GitHub repositories. Never execute installers."""
from pathlib import Path, PurePosixPath
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .storage import AddonError, atomic, digest

REPOS = {'optiscaler': 'optiscaler/OptiScaler', 'scalpel': 'scalpelpoe/scalpel'}
MAX_DOWNLOAD = 350 * 1024 * 1024


def validate_url(url, repo=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise AddonError('The download URL is not a trusted HTTPS source.')
    if repo and (parsed.hostname != 'github.com' or not parsed.path.startswith('/' + repo + '/releases/download/')):
        raise AddonError('The asset is not hosted in the official upstream repository.')
    if not repo and parsed.hostname not in {'api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'github-releases.githubusercontent.com'}:
        raise AddonError('The download redirected outside GitHub release hosting.')


def fetch(url, limit, destination=None):
    validate_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'omarchy-poe2/1.0', 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            validate_url(response.url)
            if int(response.headers.get('Content-Length', '0')) > limit:
                raise AddonError('Download exceeds the allowed size.')
            chunks = []
            total = 0
            out = destination.open('wb') if destination else None
            try:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise AddonError('Download exceeds the allowed size.')
                    if out:
                        out.write(chunk)
                    else:
                        chunks.append(chunk)
                return b''.join(chunks) if not out else total
            finally:
                if out:
                    out.close()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AddonError('GitHub download failed. Check the connection or API rate limit and try again.') from exc


def latest(component):
    repo = REPOS[component]
    data = json.loads(fetch('https://api.github.com/repos/' + repo + '/releases/latest', 2 * 1024 * 1024))
    if data.get('draft') or data.get('prerelease') or not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[a-z])?', str(data.get('tag_name', ''))):
        raise AddonError('Upstream did not return a recognized stable release.')
    assets = []
    for asset in data.get('assets', []):
        name = asset.get('name', '')
        matches = (component == 'scalpel' and name == 'Scalpel.AppImage') or (component == 'optiscaler' and name.lower().endswith('.7z') and name.lower().startswith('optiscaler'))
        if matches:
            validate_url(asset.get('browser_download_url', ''), repo)
            checksum = asset.get('digest', '') or ''
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', checksum):
                raise AddonError('The upstream asset has no SHA-256 digest. Automatic installation was stopped.')
            size = asset.get('size', 0)
            if not isinstance(size, int) or not 1024 < size <= MAX_DOWNLOAD:
                raise AddonError('The upstream asset size is invalid.')
            assets.append({'tag': data['tag_name'], 'name': name, 'url': asset['browser_download_url'], 'sha256': checksum[7:], 'size': size})
    if len(assets) != 1:
        raise AddonError('Expected exactly one supported Linux release asset.')
    return assets[0]


def download(release, cache):
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (release['sha256'] + '-' + release['name'])
    if target.exists() and digest(target.read_bytes()) == release['sha256']:
        return target
    if shutil.disk_usage(cache).free < release['size'] * 4 + 128 * 1024 * 1024:
        raise AddonError('Not enough free disk space to stage this release safely.')
    fd, name = tempfile.mkstemp(dir=cache)
    os.close(fd)
    temporary = Path(name)
    try:
        size = fetch(release['url'], min(MAX_DOWNLOAD, release['size'] + 1), temporary)
        if size != release['size'] or digest(temporary.read_bytes()) != release['sha256']:
            raise AddonError('The download checksum or size does not match GitHub release metadata.')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def extract(archive, destination):
    if not shutil.which('bsdtar'):
        raise AddonError('bsdtar is required for OptiScaler archives. Install the libarchive package.')
    try:
        listing = subprocess.run(['bsdtar', '-tf', str(archive)], check=True, capture_output=True, timeout=30).stdout.decode()
        names = listing.splitlines()
        if not names or len(names) > 1000:
            raise AddonError('Unexpected OptiScaler archive contents.')
        for name in names:
            path = PurePosixPath(name.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in name or len(name) > 300:
                raise AddonError('An archive entry has an unsafe path.')
        types = subprocess.run(['bsdtar', '-tvf', str(archive)], check=True, capture_output=True, timeout=30).stdout.decode()
        if any(line and line[0] not in {'-', 'd'} for line in types.splitlines()):
            raise AddonError('Links and special files are not allowed in release archives.')
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run(['bsdtar', '--no-same-owner', '--no-same-permissions', '-xf', str(archive), '-C', str(destination)], check=True, capture_output=True, timeout=60)
        size = 0
        for path in destination.rglob('*'):
            if path.is_symlink() or not path.resolve().is_relative_to(destination.resolve()):
                raise AddonError('An archive entry escaped its staging directory.')
            if path.is_file():
                size += path.stat().st_size
        if size > 1024 * 1024 * 1024:
            raise AddonError('The extracted release is unexpectedly large.')
    except subprocess.SubprocessError as exc:
        raise AddonError('Could not safely extract the OptiScaler archive.') from exc
