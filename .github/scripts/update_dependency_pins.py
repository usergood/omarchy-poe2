"""Prepare a patch release when a managed tool has a newer stable release."""
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from prepare_release import metadata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from poe2 import releases
from poe2.storage import digest

ASSET_NAMES = {
    'optiscaler': re.compile(r'OptiScaler[_-][A-Za-z0-9._-]+\.7z', re.IGNORECASE | re.ASCII),
    'scalpel': re.compile(r'Scalpel\.AppImage'),
    'pob_redux': re.compile(r'PoB\.Redux_\d+\.\d+\.\d+[a-z]?_amd64\.AppImage', re.ASCII),
}
DISPLAY_NAMES = {'optiscaler': 'OptiScaler', 'scalpel': 'Scalpel', 'pob_redux': 'PoB Redux'}


def version_key(tag):
    if not releases.STABLE_TAG.fullmatch(tag):
        raise ValueError(f'Unrecognized stable tag: {tag!r}')
    major, minor, patch = tag.removeprefix('v').split('.')
    suffix = ''
    if patch[-1].isalpha():
        patch, suffix = patch[:-1], patch[-1]
    return int(major), int(minor), int(patch), suffix


def new_pin(component, current):
    repo = releases.REPOS[component]
    upstream = json.loads(releases.fetch(f'https://api.github.com/repos/{repo}/releases/latest', 2 * 1024 * 1024))
    tag = upstream['tag_name']
    if upstream['draft'] or upstream['prerelease']:
        raise ValueError(f'{repo} did not return a published stable release.')
    if version_key(tag) <= version_key(current['tag']):
        return None

    assets = [asset for asset in upstream['assets'] if ASSET_NAMES[component].fullmatch(asset['name'])]
    if len(assets) != 1:
        raise ValueError(f'{repo} {tag} must have exactly one matching release asset.')
    asset = assets[0]
    name, size, checksum = asset['name'], asset['size'], asset.get('digest') or ''
    if (asset['state'] != 'uploaded' or not 1024 < size <= releases.MAX_DOWNLOAD
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', checksum)):
        raise ValueError(f'{repo} {tag} has invalid asset metadata for {name}.')
    url = f'https://github.com/{repo}/releases/download/{tag}/{name}'
    if asset['browser_download_url'] != url:
        raise ValueError(f'{repo} {tag} has an unexpected asset URL for {name}.')

    with TemporaryDirectory() as directory:
        download = Path(directory) / name
        if releases.fetch(url, size, download) != size or digest(download.read_bytes()) != checksum[7:]:
            raise ValueError(f'{repo} {tag} failed size or SHA-256 verification for {name}.')
    return {'tag': tag, 'name': name, 'size': size, 'sha256': checksum[7:]}


def update(root):
    pins_path = root / 'poe2/release-pins.json'
    pins = json.loads(pins_path.read_text())
    notes = []
    for component, repo in releases.REPOS.items():
        pin = new_pin(component, pins[component])
        if pin is not None:
            previous_tag = pins[component]['tag']
            tag = pin['tag']
            notes.append(f'- Update {DISPLAY_NAMES[component]} from {previous_tag} to '
                         f'[{tag}](https://github.com/{repo}/releases/tag/{tag}).')
            pins[component] = pin
    if not notes:
        return False

    old_version = metadata(root)[0][1:]
    major, minor, patch = old_version.split('.')
    version = f'{major}.{minor}.{int(patch) + 1}'
    manifest = root / 'manifest.json'
    backend = root / 'poe2/__init__.py'
    changelog = root / 'CHANGELOG.md'
    manifest_text = re.sub(r'("version"\s*:\s*)"' + re.escape(old_version) + '"',
                           lambda match: f'{match[1]}"{version}"', manifest.read_text(), count=1)
    backend_text = re.sub(r'^(__version__\s*=\s*)([\'\"])' + re.escape(old_version) + r'\2',
                          lambda match: f'{match[1]}{match[2]}{version}{match[2]}',
                          backend.read_text(), count=1, flags=re.M)
    changelog_text = changelog.read_text().replace(f'## {old_version}\n',
                                                  f'## {version}\n\n' + '\n'.join(notes) + f'\n\n## {old_version}\n', 1)
    pins_path.write_text(json.dumps(pins, indent=2) + '\n')
    manifest.write_text(manifest_text)
    backend.write_text(backend_text)
    changelog.write_text(changelog_text)
    metadata(root)
    return True


if __name__ == '__main__':
    if update(ROOT):
        print('Prepared ' + metadata(ROOT)[0] + ' with updated dependency pins.')
    else:
        print('The dependency pins are current.')
