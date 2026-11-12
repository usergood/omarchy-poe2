"""Atomic file changes, immutable backups, and crash recovery."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile


class AddonError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def atomic(path, data, executable=False):
    path = Path(path)
    if path.is_symlink():
        raise AddonError('Refusing to replace a symbolic link: ' + path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if path.exists():
            shutil.copymode(path, name)
        if executable:
            os.chmod(name, 0o755)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'blobs').mkdir(exist_ok=True)

    def put(self, data):
        if data is None:
            return None
        key = digest(data)
        path = self.root / 'blobs' / key
        if not path.exists():
            atomic(path, data)
        return key

    def get(self, key):
        if key is None:
            return None
        data = (self.root / 'blobs' / key).read_bytes()
        if digest(data) != key:
            raise AddonError('A backup checksum failed; no changes were applied.')
        return data

    def recover(self):
        journal = self.root / 'transaction.json'
        if not journal.exists():
            return
        for entry in load(journal):
            path = Path(entry['path'])
            data = self.get(entry['before'])
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path, data)
        journal.unlink()

    def commit(self, plan):
        """All old contents are durable before the first destination is changed."""
        journal = self.root / 'transaction.json'
        if journal.exists():
            raise AddonError('An unfinished operation needs recovery. Close Steam and run Repair.')
        entries = []
        for path in plan:
            if path.is_symlink():
                raise AddonError('Refusing to modify a symbolic link: ' + path.name)
            entries.append({'path': str(path), 'before': self.put(path.read_bytes() if path.exists() else None)})
        atomic(journal, json_bytes(entries))
        try:
            for path, data in plan.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic(path, data)
        except BaseException:
            self.recover()
            raise
        journal.unlink()
