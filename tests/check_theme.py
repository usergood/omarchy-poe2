"""Exercise live theme bindings in an isolated, offscreen Omarchy QML host."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    project = Path(__file__).resolve().parents[1]
    shell = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy')) / 'shell'
    with tempfile.TemporaryDirectory(prefix='poe2-theme-test-') as directory:
        root = Path(directory)
        # Quickshell resolves qs.* imports relative to its config root.
        for path in shell.iterdir():
            if path.is_dir():
                (root / path.name).symlink_to(path, target_is_directory=True)
        qml = (project / 'tests/theme-smoke.qml').read_text().replace('@PLUGIN_URL@', project.as_uri())
        (root / 'shell.qml').write_text(qml)
        result = subprocess.run(['quickshell', '-p', str(root)],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or 'POE2_THEME_TEST: PASS' not in output or 'POE2_THEME_TEST: FAIL' in output:
            print(output)
            return 1
        print('Live popup palette test passed (same controls, dark → light).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
