"""Steam discovery and lossless, scoped configuration edits."""
from dataclasses import dataclass
from pathlib import Path
import os
import re

from .storage import AddonError

APPID = '2694490'
DISPLAY_KEYS = {'renderer_type', 'upscale', 'upscale_quality', 'upscale_quality_xess', 'upscale_resolution', 'use_dynamic_resolution'}


@dataclass
class Entry:
    key: str
    value: object
    start: int
    end: int
    value_start: int
    value_end: int


def unescape(value):
    return re.sub(r'\\([\\"])', r'\1', value)


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def parse(text):
    tokens = [m for m in re.finditer(r'"(?:\\.|[^"\\])*"|[{}]|//[^\n]*', text) if not m[0].startswith('//')]
    pos = 0
    def walk(nested=False):
        nonlocal pos
        entries = []
        while pos < len(tokens):
            key = tokens[pos]
            if key[0] == '}':
                if not nested:
                    raise AddonError('Unexpected brace in Steam configuration')
                pos += 1
                return entries, key.start(), key.end()
            if not key[0].startswith('"'):
                raise AddonError('Invalid Steam configuration')
            pos += 1
            if pos == len(tokens):
                raise AddonError('Incomplete Steam configuration')
            value = tokens[pos]
            pos += 1
            if value[0] == '{':
                children, close, end = walk(True)
                entries.append(Entry(unescape(key[0][1:-1]), children, key.start(), end, value.end(), close))
            elif value[0].startswith('"'):
                entries.append(Entry(unescape(key[0][1:-1]), unescape(value[0][1:-1]), key.start(), value.end(), value.start(), value.end()))
            else:
                raise AddonError('Invalid Steam value')
        if nested:
            raise AddonError('Unclosed Steam configuration block')
        return entries, len(text), len(text)
    return walk()[0]


def object_dict(entries):
    return {e.key: object_dict(e.value) if isinstance(e.value, list) else e.value for e in entries}


def child(entries, key):
    found = [e for e in entries if e.key.lower() == key.lower()]
    if len(found) != 1:
        raise AddonError('Cannot uniquely locate Steam setting: ' + key)
    return found[0]


def app_entry(text):
    entries = parse(text)
    for key in ['UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps', APPID]:
        node = child(entries, key)
        if not isinstance(node.value, list):
            raise AddonError('Invalid Steam application settings')
        entries = node.value
    return node


def launch_read(text):
    entries = app_entry(text).value
    return next((e.value for e in entries if e.key.lower() == 'launchoptions'), None)


def launch_write(text, options):
    node = app_entry(text)
    current = [e for e in node.value if e.key.lower() == 'launchoptions']
    if len(current) > 1:
        raise AddonError('Duplicate Steam launch options; resolve them before changing profiles')
    if current:
        entry = current[0]
        if options is None:
            return text[:entry.start] + text[entry.end:]
        return text[:entry.value_start] + quote(options) + text[entry.value_end:]
    if options is None:
        return text
    insertion = '\n\t\t\t\t\t\t"LaunchOptions"\t\t' + quote(options) + '\n\t\t\t\t\t'
    return text[:node.value_end] + insertion + text[node.value_end:]


def display_read(data):
    section = ''
    values = {}
    for line in data.decode('utf-8-sig').splitlines():
        if line.strip().startswith('['):
            section = line.strip()
        elif section == '[DISPLAY]' and '=' in line:
            key, value = line.split('=', 1)
            if key.strip() in DISPLAY_KEYS:
                values[key.strip()] = value.strip()
    if not values:
        raise AddonError('PoE 2 graphics settings are missing. Launch the game once, then exit it.')
    return values


def display_write(data, values):
    display_read(data)
    text = data.decode('utf-8-sig')
    block = re.search(r'(?ms)^\[DISPLAY\]\s*\n(.*?)(?=^\[|\Z)', text)
    if not block:
        raise AddonError('Cannot locate PoE 2 display settings')
    body = block[1]
    for key in DISPLAY_KEYS:
        pattern = r'(?m)^\s*' + re.escape(key) + r'\s*=.*$'
        if key in values:
            replacement = key + '=' + values[key]
            if re.search(pattern, body):
                body = re.sub(pattern, lambda _: replacement, body)
            else:
                body = body.rstrip() + '\n' + replacement + '\n'
        else:
            body = re.sub(pattern + r'\n?', '', body)
    return ('\ufeff' + text[:block.start(1)] + body + text[block.end(1):]).encode()


def processes():
    found = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            comm = (proc / 'comm').read_text().strip().lower()
            exe = Path(os.readlink(proc / 'exe')).name.lower()
            if exe == 'steam' or comm == 'steam':
                found.add('steam')
            if comm.startswith('pathofexile') or exe.startswith('pathofexile'):
                found.add('game')
            if exe == 'scalpel' or comm == 'scalpel':
                found.add('scalpel')
        except OSError:
            pass
    return sorted(found)


def require_closed():
    if {'game', 'steam'} & set(processes()):
        raise AddonError('Exit PoE 2 and fully exit Steam before changing game files or settings.')


def discover(home=None, override=None, account=None):
    home = Path(home or Path.home())
    roots = [Path(override)] if override else [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root']
    roots = list(dict.fromkeys(p.resolve() for p in roots if p.exists()))
    for root in roots:
        libraries = [root]
        folders = root / 'steamapps/libraryfolders.vdf'
        if folders.exists():
            data = object_dict(parse(folders.read_text())).get('libraryfolders', {})
            for value in data.values():
                if isinstance(value, dict) and 'path' in value:
                    libraries.append(Path(value['path']))
        for library in dict.fromkeys(libraries):
            manifest = library / ('steamapps/appmanifest_' + APPID + '.acf')
            if not manifest.exists():
                continue
            data = object_dict(parse(manifest.read_text())).get('AppState', {})
            game = (library / 'steamapps/common' / data.get('installdir', '')).resolve()
            if data.get('appid') != APPID or not (game / 'PathOfExileSteam.exe').is_file():
                continue
            prefix = library / 'steamapps/compatdata' / APPID / 'pfx'
            configs = [prefix / 'drive_c/users/steamuser/Documents/My Games/Path of Exile 2/poe2_production_Config.ini']
            config = next((p.resolve() for p in configs if p.is_file()), None)
            users = root / 'userdata'
            accounts = [p for p in users.glob('*/config/localconfig.vdf') if p.is_file()]
            if account:
                accounts = [p for p in accounts if p.parent.parent.name == str(account)]
            candidates = []
            for path in accounts:
                try:
                    launch_read(path.read_text())
                    candidates.append(path.resolve())
                except (AddonError, UnicodeError):
                    pass
            if len(candidates) > 1:
                login = root / 'config/loginusers.vdf'
                most_recent = []
                if login.exists():
                    for sid, value in object_dict(parse(login.read_text())).get('users', {}).items():
                        if isinstance(value, dict) and value.get('MostRecent') == '1' and sid.isdigit():
                            most_recent.append(str(int(sid) - 76561197960265728))
                recent = [p for p in candidates if p.parent.parent.name in most_recent]
                if len(recent) == 1:
                    candidates = recent
            return {'root': str(root), 'game': str(game), 'manifest': str(manifest.resolve()),
                    'build': data.get('buildid', ''), 'config': str(config) if config else None,
                    'steam_config': str(candidates[0]) if len(candidates) == 1 else None,
                    'account_ambiguous': len(candidates) > 1,
                    'installed': bool(int(data.get('StateFlags', '0')) & 4)}
    return None


def fsr4_launch(options):
    """Merge only the dxgi override; preserve unrelated wrappers and user arguments."""
    text = options or '%command%'
    if '%command%' not in text:
        raise AddonError('Launch options need %command%; edit them in Steam before enabling FSR4.')
    pattern = r'''\bWINEDLLOVERRIDES=(?:"([^"\n]*)"|'([^'\n]*)'|([^\s]+))'''
    match = re.search(pattern, text)
    if match:
        value = next(v for v in match.groups() if v is not None)
        parts = [p for p in value.split(';') if p]
        others = []
        for part in parts:
            names, sep, backend = part.partition('=')
            remaining = [n for n in names.split(',') if n.lower().removesuffix('.dll') != 'dxgi']
            if remaining:
                others.append(','.join(remaining) + (sep + backend if sep else ''))
        replacement = 'WINEDLLOVERRIDES="' + ';'.join(others + ['dxgi=n,b']) + '"'
        return text[:match.start()] + replacement + text[match.end():]
    # Environment assignments must precede command wrappers such as gamemoderun.
    return 'WINEDLLOVERRIDES="dxgi=n,b" ' + text


def compatibility_tool(root):
    path = Path(root) / 'config/config.vdf'
    if not path.exists():
        return ''
    try:
        def search(entries):
            for entry in entries:
                if isinstance(entry.value, list):
                    if entry.key.lower() == 'compattoolmapping':
                        app = next((e for e in entry.value if e.key == APPID), None)
                        if app and isinstance(app.value, list):
                            return next((e.value for e in app.value if e.key.lower() == 'name'), '')
                    found = search(entry.value)
                    if found:
                        return found
            return ''
        return search(parse(path.read_text()))
    except (OSError, AddonError):
        return ''


def without_fsr4_override(options):
    if options is None:
        return None
    pattern = r'''\bWINEDLLOVERRIDES=(?:"([^"\n]*)"|'([^'\n]*)'|([^\s]+))'''
    match = re.search(pattern, options)
    if not match:
        return options
    value = next(v for v in match.groups() if v is not None)
    parts = []
    for part in value.split(';'):
        names, sep, backend = part.partition('=')
        names = [n for n in names.split(',') if n and n.lower().removesuffix('.dll') != 'dxgi']
        if names:
            parts.append(','.join(names) + (sep + backend if sep else ''))
    replacement = 'WINEDLLOVERRIDES="' + ';'.join(parts) + '"' if parts else ''
    return (options[:match.start()] + replacement + options[match.end():]).strip()
