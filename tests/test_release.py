import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.github/scripts'
with patch.object(sys, 'path', [str(SCRIPTS), *sys.path]):
    import prepare_release as release
    import update_dependency_pins as updater


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'poe2').mkdir()
        (self.root / 'manifest.json').write_text(json.dumps({'version': '1.1.0'}))
        (self.root / 'poe2/__init__.py').write_text("__version__ = '1.1.0'\n")
        (self.root / 'CHANGELOG.md').write_text('# Changelog\n\n## 1.1.0\n\n- New panel.\n\n## 1.0.0\n\n- Original release.\n')

    def test_notes_include_only_the_version_being_released(self):
        self.assertEqual(release.metadata(self.root), ('v1.1.0', '- New panel.\n'))

    def test_version_mismatch_blocks_release(self):
        (self.root / 'poe2/__init__.py').write_text("__version__ = '1.0.0'\n")
        with self.assertRaisesRegex(ValueError, 'versions must match'):
            release.metadata(self.root)

    def test_missing_notes_block_release(self):
        (self.root / 'CHANGELOG.md').write_text('# Changelog\n\n## Unreleased\n\n- New panel.\n')
        with self.assertRaisesRegex(ValueError, 'Add release notes'):
            release.metadata(self.root)

    def test_empty_notes_block_release(self):
        (self.root / 'CHANGELOG.md').write_text('# Changelog\n\n## 1.1.0\n\n## 1.0.0\n\n- Old release.\n')
        with self.assertRaisesRegex(ValueError, 'Add release notes'):
            release.metadata(self.root)

    def test_invalid_version_blocks_release(self):
        (self.root / 'manifest.json').write_text(json.dumps({'version': '1.1.0-beta'}))
        with self.assertRaisesRegex(ValueError, 'stable'):
            release.metadata(self.root)

    def upstream(self, tag, component):
        repo = updater.releases.REPOS[component]
        name = updater.releases.PINS[component]['name']
        url = f'https://github.com/{repo}/releases/download/{tag}/{name}'
        payload = component.encode() * 1024
        return {
            'tag_name': tag, 'draft': False, 'prerelease': False,
            'assets': [{'name': name, 'size': len(payload), 'state': 'uploaded',
                        'digest': 'sha256:' + updater.digest(payload), 'browser_download_url': url}],
        }, payload

    def run_update(self, optiscaler, scalpel):
        pins = self.root / 'poe2/release-pins.json'
        pins.write_text(json.dumps(updater.releases.PINS))
        responses = {updater.releases.REPOS['optiscaler']: optiscaler,
                     updater.releases.REPOS['scalpel']: scalpel}

        def fetch(url, limit, destination=None):
            for repo, (metadata, payload) in responses.items():
                if url == f'https://api.github.com/repos/{repo}/releases/latest':
                    return json.dumps(metadata).encode()
                if url == metadata['assets'][0]['browser_download_url']:
                    self.assertEqual(limit, metadata['assets'][0]['size'])
                    destination.write_bytes(payload)
                    return len(payload)
            self.fail(f'Unexpected download: {url}')

        with patch.object(updater.releases, 'fetch', side_effect=fetch) as network:
            changed = updater.update(self.root)
        return changed, json.loads(pins.read_text()), network.call_count

    def test_current_or_older_tags_do_not_download_assets_or_bump_version(self):
        current = updater.releases.PINS['optiscaler']['tag']
        changed, pins, requests = self.run_update(self.upstream(current, 'optiscaler'),
                                                  self.upstream('v0.0.1', 'scalpel'))
        self.assertFalse(changed)
        self.assertEqual(requests, 2)
        self.assertEqual(pins, updater.releases.PINS)
        self.assertEqual(release.metadata(self.root)[0], 'v1.1.0')

    def test_two_upstream_updates_create_one_patch_version(self):
        optiscaler = self.upstream('v99.1.0', 'optiscaler')
        scalpel = self.upstream('v99.2.0', 'scalpel')
        changed, pins, requests = self.run_update(optiscaler, scalpel)
        self.assertTrue(changed)
        self.assertEqual(requests, 4)
        tag, notes = release.metadata(self.root)
        self.assertEqual(tag, 'v1.1.1')
        for component, (metadata, payload) in [('optiscaler', optiscaler), ('scalpel', scalpel)]:
            self.assertEqual(pins[component], {'tag': metadata['tag_name'], 'size': len(payload),
                                               'name': metadata['assets'][0]['name'], 'sha256': updater.digest(payload)})
            self.assertIn(metadata['tag_name'], notes)

    def test_failed_asset_verification_leaves_both_pins_and_version_intact(self):
        optiscaler = self.upstream('v99.1.0', 'optiscaler')
        metadata, payload = self.upstream('v99.2.0', 'scalpel')
        with self.assertRaisesRegex(ValueError, 'failed size or SHA-256 verification'):
            self.run_update(optiscaler, (metadata, b'x' * len(payload)))
        self.assertEqual(json.loads((self.root / 'poe2/release-pins.json').read_text()), updater.releases.PINS)
        self.assertEqual(release.metadata(self.root)[0], 'v1.1.0')
