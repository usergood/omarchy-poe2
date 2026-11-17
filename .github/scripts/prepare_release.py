"""Validate the release version and extract notes without publishing anything."""
import argparse
import ast
import json
from pathlib import Path
import re


def metadata(root):
    version = json.loads((root / 'manifest.json').read_text())['version']
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('The manifest must contain a stable major.minor.patch version.')
    module = ast.parse((root / 'poe2/__init__.py').read_text())
    backend = next((ast.literal_eval(node.value) for node in module.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == '__version__'
                            for target in node.targets)), None)
    if backend != version:
        raise ValueError('Manifest and backend versions must match before release.')
    changelog = (root / 'CHANGELOG.md').read_text()
    match = re.search(r'^## ' + re.escape(version) + r'\s*\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    if not match or not match.group(1).strip():
        raise ValueError('Add release notes under ## ' + version + ' in CHANGELOG.md.')
    return 'v' + version, match.group(1).strip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes-file', type=Path)
    args = parser.parse_args()
    tag, notes = metadata(Path(__file__).resolve().parents[2])
    if args.notes_file:
        args.notes_file.write_text(notes)
    print('tag=' + tag)


if __name__ == '__main__':
    main()
