import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / '.github/scripts/prepare_release.py'
spec = importlib.util.spec_from_file_location('prepare_release', SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


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
