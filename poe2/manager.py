"""Versioned, reversible game integration and application launchers."""
from pathlib import Path, PurePosixPath
import configparser
import copy
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time

from . import __version__
from . import releases, steam
from .optiscaler import configure, validate_preferences
from .storage import AddonError, Store, atomic, digest, json_bytes, load

DEFAULTS = {'quality': 'Quality', 'watermark': False, 'diagnostics': False,
            'menu_key': '0xDC', 'auto_scalpel': True, 'steam_root': '', 'account': ''}
TRADE_URL = 'https://www.pathofexile.com/trade2'


class Manager:
    def __init__(self, root=None, home=None):
        self.home = Path(home or Path.home())
        self.root = Path(root or os.environ.get('POE2_ADDON_DATA', self.home / '.local/share/omarchy/poe2-addon'))
        self.store = Store(self.root)
        self.state_path = self.root / 'installation.json'
        self.preferences_path = self.root / 'preferences.json'
        self.state = load(self.state_path)
        self.preferences = dict(DEFAULTS, **load(self.preferences_path, {}))
        self.hash_cache = load(self.root / 'hash-cache.json', {})
        self.recovered = False

    def info(self):
        return steam.discover(self.home, self.preferences['steam_root'] or None, self.preferences['account'] or None)

    def file_hash(self, path):
        path = Path(path)
        if path.is_symlink():
            raise AddonError('A managed game file became a symbolic link: ' + path.name)
        if not path.exists():
            return None
        st = path.stat()
        signature = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
        entry = self.hash_cache.get(str(path))
        if entry and entry['stat'] == signature:
            return entry['sha256']
        key = digest(path.read_bytes())
        self.hash_cache[str(path)] = {'stat': signature, 'sha256': key}
        return key

    def save_cache(self):
        atomic(self.root / 'hash-cache.json', json_bytes(self.hash_cache))

    def require_game(self):
        info = self.info()
        if not info or not info['installed']:
            raise AddonError('Install Path of Exile 2 in native Steam first, then launch it once.')
        if not info['config']:
            raise AddonError('Launch PoE 2 once and exit it so its graphics configuration is created.')
        if info['account_ambiguous']:
            raise AddonError('Multiple Steam accounts contain PoE 2. Select an account with configure --account ACCOUNT_ID.')
        if not info['steam_config']:
            raise AddonError('Sign in to Steam and launch PoE 2 once before setting up FSR4.')
        if self.state and self.state['game'] != info['game']:
            raise AddonError('The game moved to another library. Restore Original in the old library before setting up the new installation.')
        return info

    def prepare(self):
        steam.require_closed()
        if (self.root / 'transaction.json').exists():
            self.store.recover()
            self.state = load(self.state_path)
            self.recovered = True

    def payload(self, state=None):
        state = state or self.state
        if not state or not state.get('release'):
            raise AddonError('OptiScaler is not installed through this addon. Install FSR4 from Tools first.')
        directory = self.root / 'payloads' / state['release']['id']
        mapping = load(directory / 'files.json')
        if not mapping:
            raise AddonError('The saved OptiScaler payload is missing. Refresh the FSR4 installation from Tools.')
        for rel in mapping:
            p = PurePosixPath(rel)
            if p.is_absolute() or '..' in p.parts or ':' in rel:
                raise AddonError('The saved payload contains an invalid path.')
        result = {rel: self.store.get(key) for rel, key in mapping.items()}
        if 'dxgi.dll' not in result or 'OptiScaler.ini' not in result:
            raise AddonError('The saved payload is incomplete.')
        return result

    def health(self, info=None):
        info = info if info is not None else self.info()
        if not info:
            return 'missing', 'Install PoE 2 in Steam to begin.'
        if not self.state:
            if (Path(info['game']) / 'dxgi.dll').exists():
                return 'unmanaged', 'An existing dxgi.dll needs to be adopted or removed before setup.'
            return 'original', 'Original game files; FSR4 has not been set up in this addon.'
        if self.state['game'] != info['game']:
            return 'needs_repair', 'The Steam library path changed.'
        if self.state.get('build') != info['build']:
            return 'needs_repair', 'Steam updated PoE 2. Repair the selected profile.'
        game = Path(info['game'])
        if self.state['mode'] == 'fsr4':
            for rel, entry in self.state['managed'].items():
                if rel == 'OptiScaler.ini':
                    continue
                if self.file_hash(game / rel) != entry['installed']:
                    return 'needs_repair', 'OptiScaler files changed or are missing.'
            try:
                current = (game / 'OptiScaler.ini').read_bytes()
                desired = configure(self.store.get(load(self.root / 'payloads' / self.state['release']['id'] / 'files.json')['OptiScaler.ini']), self.preferences, current)
                def parsed(data):
                    p = configparser.ConfigParser(interpolation=None)
                    p.read_string(data.decode('utf-8-sig'))
                    return {s: dict(p[s]) for s in p.sections()}
                if parsed(current) != parsed(desired):
                    return 'needs_repair', 'FSR4 preferences drifted. Repair reapplies your saved choices.'
                display = steam.display_read(Path(info['config']).read_bytes())
                if any(display.get(k) != v for k, v in self.fsr4_display().items()):
                    return 'needs_repair', 'PoE 2 graphics settings changed.'
                options = steam.launch_read(Path(info['steam_config']).read_text())
                if not options or not re.search(r'\bdxgi=n,b\b', options, re.I):
                    return 'needs_repair', 'The Steam DLL override is missing.'
            except (OSError, ValueError, configparser.Error, AddonError):
                return 'needs_repair', 'FSR4 configuration needs repair.'
        elif (game / 'dxgi.dll').exists():
            return 'needs_repair', 'An unexpected dxgi.dll is present in Original mode.'
        return self.state['mode'], 'Ready. FSR4 image quality and performance still depend on the game and GPU.' if self.state['mode'] == 'fsr4' else 'Ready with original game files.'

    def scalpel(self):
        metadata = load(self.root / 'scalpel.json', {})
        managed = self.root / 'apps/Scalpel.AppImage'
        if managed.exists():
            if metadata.get('sha256') != self.file_hash(managed):
                return {'available': False, 'source': 'managed', 'version': 'checksum mismatch'}
            return {'available': True, 'source': 'managed', 'version': metadata.get('tag', 'unknown'), 'path': str(managed)}
        command = shutil.which('scalpel-poe')
        if command:
            version = 'package-managed'
            if shutil.which('pacman'):
                result = subprocess.run(['pacman', '-Q', 'scalpel-poe-bin'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version = result.stdout.strip().split()[-1]
            return {'available': True, 'source': 'system', 'version': version, 'path': command}
        return {'available': False, 'source': 'none', 'version': ''}

    def scalpel_config(self):
        return Path(os.environ.get('XDG_CONFIG_HOME') or self.home / '.config') / 'scalpel/config.json'

    def scalpel_setup(self):
        """Read Scalpel's own onboarding state; installed/running is not ready."""
        try:
            with self.scalpel_config().open('rb') as source:
                raw = source.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                return 'unknown'
            config = json.loads(raw)
            if not isinstance(config, dict):
                return 'unknown'
        except FileNotFoundError:
            return 'required'
        except (OSError, ValueError, UnicodeError):
            return 'unknown'
        if config.get('onboardingCompleted') is not True:
            return 'required'
        return 'ready' if type(config.get('poeVersion')) is int and config['poeVersion'] == 2 else 'wrong_game'

    def status(self):
        info = self.info()
        profile, detail = self.health(info)
        checks = {
            'steam': bool(shutil.which('steam')), 'python': True,
            'bsdtar': bool(shutil.which('bsdtar')), 'browser': bool(shutil.which('xdg-open')),
            'hyprland': bool(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')),
            'x86_64': platform.machine() in {'x86_64', 'AMD64'},
            'config': bool(info and info['config']), 'account': bool(info and info['steam_config']),
        }
        proton = steam.compatibility_tool(info['root']) if info else ''
        checks['proton_selected'] = bool(proton)
        driver = ''
        if shutil.which('pacman'):
            result = subprocess.run(['pacman', '-Q', 'mesa'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                driver = result.stdout.strip().split()[-1]
        warnings = []
        if info and info['steam_config']:
            options = steam.launch_read(Path(info['steam_config']).read_text()) or ''
            if re.search(r'PROTON_(?:USE|ENABLE)_WAYLAND\s*=\s*[\"\']?1', options):
                warnings.append('Native Proton Wayland is enabled. Scalpel hotkeys require the XWayland game path.')
        if info and not proton:
            warnings.append('Select a recent GE-Proton or Proton Experimental in Steam Compatibility settings for FSR4.')
        if driver:
            version = driver.split(':')[-1]
            numbers = re.match(r'(\d+)\.(\d+)', version)
            if numbers and tuple(map(int, numbers.groups())) < (25, 2):
                warnings.append('Update Mesa to 25.2 or newer before using this FSR4 setup.')
        if not checks['bsdtar']:
            warnings.append('Install libarchive for OptiScaler extraction.')
        if not checks['x86_64']:
            warnings.append('Only Linux x86_64 is supported for the upstream AppImage.')
        if not checks['hyprland']:
            warnings.append('The bar widget is designed for Omarchy on Hyprland.')
        state = self.state or {}
        scalpel = dict(self.scalpel(), setup=self.scalpel_setup())
        result = {'ok': True, 'addon_version': __version__, 'profile': profile, 'selected': state.get('mode', 'original'),
                  'detail': detail, 'running': steam.processes(), 'game_installed': bool(info and info['installed']),
                  'build': info['build'] if info else '', 'proton': proton, 'mesa': driver, 'configured': bool(self.state), 'can_rollback': (self.root / 'rollback.json').exists(),
                  'optiscaler': state.get('release', {}).get('tag', ''), 'scalpel': scalpel,
                  'preferences': self.preferences, 'checks': checks, 'warnings': warnings,
                  'pinned_versions': {name: pin['tag'] for name, pin in releases.PINS.items()},
                  'updates': load(self.root / 'updates.json', {}), 'recovery': (self.root / 'transaction.json').exists()}
        self.save_cache()
        return result

    def fsr4_display(self):
        return {'renderer_type': 'DirectX12', 'upscale': 'DLSS', 'upscale_quality': self.preferences['quality'], 'use_dynamic_resolution': 'false'}

    def baseline(self, info):
        return {'schema': 1, 'game': info['game'], 'build': info['build'], 'mode': 'original', 'managed': {},
                'original_display': steam.display_read(Path(info['config']).read_bytes()),
                'original_launch': steam.launch_read(Path(info['steam_config']).read_text())}

    def adopt_legacy(self, info):
        legacy = self.home / '.local/share/omarchy/poe2-profiles'
        old = load(legacy / 'settings.json')
        dll = Path(info['game']) / 'dxgi.dll'
        if not dll.exists():
            return self.baseline(info)
        if not old or old['game'] != info['game'] or self.file_hash(dll) != old['dxgi_sha256']:
            raise AddonError('An unrecognized dxgi.dll already exists. Restore the other mod before installing OptiScaler.')
        original = load(legacy / 'original/profile.json')
        mod = load(legacy / 'fsr4/profile.json')
        state = self.baseline(info)
        state.update(mode='fsr4', original_display=original['display'], installed_launch=steam.launch_read(Path(info['steam_config']).read_text()))
        # The old addon stored already escaped VDF text.
        state['original_launch'] = steam.unescape(original['launch']) if original['launch'] else None
        for i, name in enumerate(old['files']):
            rel = str(Path(name).relative_to(info['game']))
            before = (legacy / 'original/files' / str(i)).read_bytes() if i in original['present'] else None
            installed = (legacy / 'fsr4/files' / str(i)).read_bytes() if i in mod['present'] else None
            state['managed'][rel] = {'original': self.store.put(before), 'installed': self.store.put(installed)}
        return state

    def reconcile(self, state, info):
        """Accept Steam replacements only for previously game-owned files after a build change."""
        game = Path(info['game'])
        patched = state.get('build') != info['build']
        for rel, entry in state['managed'].items():
            current = self.file_hash(game / rel)
            if state['mode'] == 'original':
                if current != entry['original']:
                    if rel == 'dxgi.dll' and current is not None:
                        raise AddonError('A different dxgi.dll appeared in Original mode. No files changed.')
                    # A Steam update can add a file that previously belonged only to the addon.
                    entry['original'] = self.store.put((game / rel).read_bytes() if current else None)
                continue
            if current in {entry['installed'], entry['original'], None} or rel.endswith('.ini'):
                continue
            if patched and entry['original'] is not None:
                entry['original'] = self.store.put((game / rel).read_bytes())
            else:
                raise AddonError('Unexpected change to ' + rel + '. Restore or verify the game before repair; no files changed.')
        if state['mode'] == 'fsr4':
            options = steam.launch_read(Path(info['steam_config']).read_text())
            if options != state.get('installed_launch'):
                original = steam.without_fsr4_override(options)
                if original == '%command%' and state.get('original_launch') is None:
                    original = None
                state['original_launch'] = original
        state['build'] = info['build']

    def stage_release(self, release, archive):
        if not platform.machine() in {'x86_64', 'AMD64'}:
            raise AddonError('This release supports Linux x86_64 only.')
        with tempfile.TemporaryDirectory(prefix='optiscaler-', dir=self.root) as temp:
            directory = Path(temp) / 'files'
            releases.extract(archive, directory)
            dlls = list(directory.rglob('OptiScaler.dll'))
            if len(dlls) != 1:
                raise AddonError('The release is missing a unique OptiScaler.dll.')
            base = dlls[0].parent
            payload = {}
            for path in base.rglob('*'):
                if not path.is_file():
                    continue
                rel = path.relative_to(base).as_posix()
                # Include the official SDKs and licenses, never execute or install setup scripts.
                if path.suffix.lower() not in {'.dll', '.ini'} and not rel.startswith('Licenses/'):
                    continue
                if rel == 'OptiScaler.dll':
                    rel = 'dxgi.dll'
                payload[rel] = path.read_bytes()
            if 'OptiScaler.ini' not in payload:
                raise AddonError('The archive has no configuration template.')
            configure(payload['OptiScaler.ini'], self.preferences)
            key = release['sha256']
            mapping = {rel: self.store.put(data) for rel, data in payload.items()}
            atomic(self.root / 'payloads' / key / 'files.json', json_bytes(mapping))
            return dict(release, id=key)

    def apply(self, info, state, mode):
        game = Path(info['game'])
        plan = {}
        payload = self.payload(state) if mode == 'fsr4' else {}
        previous_ini = (game / 'OptiScaler.ini').read_bytes() if (game / 'OptiScaler.ini').exists() and state['mode'] == 'fsr4' else None
        for rel in payload:
            if rel not in state['managed']:
                target = game / rel
                state['managed'][rel] = {'original': self.store.put(target.read_bytes() if target.exists() else None), 'installed': None}
        for rel, entry in state['managed'].items():
            if mode == 'fsr4' and rel in payload:
                data = configure(payload[rel], self.preferences, previous_ini) if rel == 'OptiScaler.ini' else payload[rel]
                entry['installed'] = self.store.put(data)
            else:
                data = self.store.get(entry['original'])
                if mode == 'fsr4':
                    entry['installed'] = entry['original']
            plan[game / rel] = data
        config = Path(info['config'])
        current_display = steam.display_read(config.read_bytes())
        if state['mode'] == 'original':
            state['original_display'] = current_display
            state['original_launch'] = steam.launch_read(Path(info['steam_config']).read_text())
        display = dict(current_display, **self.fsr4_display()) if mode == 'fsr4' else state['original_display']
        options = steam.fsr4_launch(state['original_launch']) if mode == 'fsr4' else state['original_launch']
        plan[config] = steam.display_write(config.read_bytes(), display)
        steam_config = Path(info['steam_config'])
        plan[steam_config] = steam.launch_write(steam_config.read_text(), options).encode()
        state['installed_launch'] = options if mode == 'fsr4' else None
        state['mode'] = mode
        state['build'] = info['build']
        state['changed_at'] = int(time.time())
        plan[self.state_path] = json_bytes(state)
        plan[self.preferences_path] = json_bytes(self.preferences)
        self.store.commit(plan)
        self.state = state
        self.hash_cache = {}
        return self.status()

    def install_optiscaler(self):
        self.prepare()
        info = self.require_game()
        state = copy.deepcopy(self.state or self.adopt_legacy(info))
        self.reconcile(state, info)
        release, archive = releases.download('optiscaler', self.root / 'cache')
        staged = self.stage_release(release, archive)
        if self.state and self.state.get('release', {}).get('id') != staged['id']:
            # Keep the complete prior registry; its payload and backup blobs are immutable.
            atomic(self.root / 'rollback.json', json_bytes(self.state))
        state['release'] = staged
        return self.apply(info, state, 'fsr4')

    def switch(self, mode):
        self.prepare()
        info = self.require_game()
        if not self.state:
            if mode == 'original' and not (Path(info['game']) / 'dxgi.dll').exists():
                return self.status()
            raise AddonError('Install FSR4 from Tools to initialize the addon first.')
        state = copy.deepcopy(self.state)
        self.reconcile(state, info)
        return self.apply(info, state, mode)

    def repair(self):
        if not self.state:
            return self.install_optiscaler()
        return self.switch(self.state['mode'])

    def rollback(self):
        self.prepare()
        info = self.require_game()
        previous = load(self.root / 'rollback.json')
        if not previous:
            raise AddonError('There is no previous OptiScaler version to restore.')
        state = copy.deepcopy(self.state)
        self.reconcile(state, info)
        self.payload(previous)
        state['release'] = previous['release']
        return self.apply(info, state, state['mode'])

    def configure(self, changes):
        preferences = dict(self.preferences, **changes)
        validate_preferences(preferences)
        if any(k in changes for k in ['steam_root', 'account']) and self.state:
            if preferences['steam_root'] != self.preferences['steam_root'] or preferences['account'] != self.preferences['account']:
                raise AddonError('Restore and uninstall FSR4 before selecting another Steam installation or account.')
        self.prepare()
        self.preferences = preferences
        if self.state and self.state['mode'] == 'fsr4':
            return self.repair()
        atomic(self.preferences_path, json_bytes(preferences))
        return self.status()

    def reset_setup(self):
        self.prepare()
        if self.state:
            if self.state['mode'] != 'original':
                raise AddonError('Select Original before resetting setup. Game files must be restored first.')
            if (Path(self.state['game']) / 'dxgi.dll').exists():
                raise AddonError('An unexpected dxgi.dll remains; restore it before resetting setup.')
            retired = self.root / 'retired-installations' / (str(time.time_ns()) + '.json')
            self.store.commit({retired: json_bytes(self.state), self.state_path: None})
            self.state = None
        return self.status()

    def check_updates(self):
        result = {'checked_at': int(time.time())}
        for component in releases.REPOS:
            try:
                result[component] = {'latest': releases.latest_tag(component)}
            except AddonError as exc:
                result[component] = {'error': str(exc)}
        atomic(self.root / 'updates.json', json_bytes(result))
        return self.status()

    def install_scalpel(self):
        if 'scalpel' in steam.processes():
            raise AddonError('Exit Scalpel before replacing its AppImage.')
        if platform.machine() not in {'x86_64', 'AMD64'}:
            raise AddonError('The upstream Scalpel AppImage supports x86_64 only.')
        release, archive = releases.download('scalpel', self.root / 'cache')
        app = self.root / 'apps/Scalpel.AppImage'
        old = load(self.root / 'scalpel.json')
        if app.exists() and old:
            backup = self.root / 'apps/Scalpel.previous.AppImage'
            atomic(backup, app.read_bytes(), executable=True)
            atomic(self.root / 'scalpel.previous.json', json_bytes(old))
        self.store.commit({app: archive.read_bytes(), self.root / 'scalpel.json': json_bytes(release)})
        app.chmod(0o755)
        self.hash_cache = {}
        return self.status()

    def launch_scalpel(self, *, focus=False):
        running = 'scalpel' in steam.processes()
        if running and not focus:
            return 'Scalpel is already running.'
        info = self.scalpel()
        if not info['available']:
            raise AddonError('Install Scalpel with the addon or install scalpel-poe-bin first.')
        # Preserve existing preferences; seed PoE 2-only defaults on clean machines.
        config = self.scalpel_config()
        if not running and not config.exists():
            atomic(config, json_bytes({'poeVersion': 2, 'onboardingSelectedGames': {'poe1': False, 'poe2': True}}))
        env = dict(os.environ, XDG_SESSION_TYPE='x11')
        # This applies only to the Electron app; never to Steam or the desktop session.
        command = [info['path'], '--ozone-platform=x11']
        log = self.root / 'scalpel-launch.log'
        if log.exists() and log.stat().st_size > 2 * 1024 * 1024:
            os.replace(log, self.root / 'scalpel-launch.previous.log')
        with log.open('ab') as output:
            subprocess.Popen(command, env=env, stdout=output, stderr=output, start_new_session=True)
        # Upstream's single-instance handler shows the window on a second launch.
        if running:
            return 'Scalpel window requested.'
        return 'Scalpel launch requested.'

    def launch_game(self):
        info = self.info()
        if not info or not info['installed']:
            raise AddonError('Install Path of Exile 2 in Steam first.')
        health, _ = self.health(info)
        if health in {'needs_repair', 'unmanaged'}:
            raise AddonError('Repair the selected game profile before launching from the addon.')
        if 'game' in steam.processes():
            return 'PoE 2 is already running.'
        if not shutil.which('steam'):
            raise AddonError('The native Steam launcher is missing.')
        message = ''
        if self.preferences['auto_scalpel']:
            if self.scalpel()['available']:
                if self.scalpel_setup() != 'ready':
                    self.launch_scalpel(focus=True)
                    return 'Complete setup in Scalpel and select PoE 2, then click Launch PoE 2 again. The game has not been launched.'
                self.launch_scalpel()
            else:
                message = ' Scalpel is not installed; the game will start without it.'
        subprocess.Popen(['steam', '-applaunch', steam.APPID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return 'PoE 2 launch requested.' + message
