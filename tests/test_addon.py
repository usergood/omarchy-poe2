import configparser
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from poe2 import optiscaler, releases, steam
from poe2.manager import Manager
from poe2.storage import AddonError, Store, atomic, digest, json_bytes, load

VDF = '''"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {
"2694490" {
"nested" { "LaunchOptions" "keep nested" }
"LaunchOptions" "gamemoderun %command% --foo"
"Playtime" "123"
}
"123" { "LaunchOptions" "leave me alone" }
} } } } }'''
CONFIG = b'[LOGIN]\nseen_intro=true\n[DISPLAY]\nrenderer_type=Vulkan\nupscale=FSR\nupscale_quality=Balanced\nuse_dynamic_resolution=true\ntexture_quality=Medium\n[SOUND]\nvolume=42\n'
INI = b'''[Upscalers]\nDx12Upscaler = auto
[FSR]\nUpscalerIndex=auto\nFsr4Update=auto\nFsr4ForceEnableInt8=auto\nFsr4EnableWatermark = auto\nFsr4EnableDebugView=auto
[FrameGen]\nEnabled=auto\nFGInput=auto\nFGOutput=auto
[Spoofing]\nDxgi=auto
[Menu]\nShortcutKey=auto
[Log]\nLogLevel=auto\nLogToFile=auto
'''


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root/'home'
        self.steam = self.home/'.local/share/Steam'
        self.library = self.root/'Other Steam Library'
        self.game = self.library/'steamapps/common/Path of Exile 2'
        self.game.mkdir(parents=True)
        (self.game/'PathOfExileSteam.exe').write_bytes(b'game')
        (self.game/'libxess.dll').write_bytes(b'vanilla one')
        self.manifest = self.library/'steamapps/appmanifest_2694490.acf'
        self.build('100')
        (self.steam/'steamapps').mkdir(parents=True)
        (self.steam/'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "0" { "path" '+steam.quote(str(self.library))+' } }')
        self.local = self.steam/'userdata/123/config/localconfig.vdf'
        self.local.parent.mkdir(parents=True)
        self.local.write_text(VDF)
        self.config = self.library/'steamapps/compatdata/2694490/pfx/drive_c/users/steamuser/Documents/My Games/Path of Exile 2/poe2_production_Config.ini'
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(CONFIG)
        self.data = self.root/'data'
        fixture_pin = patch.dict(releases.PINS, optiscaler=dict(releases.PINS['optiscaler'], sha256='a'))
        fixture_pin.start()
        self.addCleanup(fixture_pin.stop)
        self.manager = Manager(self.data,self.home)
        self.config_home = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config')})
        self.config_home.start()
        self.closed = patch('poe2.steam.processes',return_value=[])
        self.closed.start()

    def tearDown(self):
        self.config_home.stop()
        self.closed.stop()
        self.temp.cleanup()

    def build(self, value):
        self.manifest.write_text('"AppState" { "appid" "2694490" "StateFlags" "4" "installdir" "Path of Exile 2" "buildid" "'+value+'" }')

    def stage(self, key='a', dll=b'OptiScaler one'):
        payload={'dxgi.dll':dll,'OptiScaler.ini':INI,'libxess.dll':b'new SDK','amd_fidelityfx_upscaler_dx12.dll':b'fsr4'}
        mapping={p:self.manager.store.put(data) for p,data in payload.items()}
        atomic(self.data/'payloads'/key/'files.json',json_bytes(mapping))
        return {'id':key,'tag':'v0.9.4','sha256':'a'*64}

    def install(self):
        info=self.manager.require_game()
        state=self.manager.baseline(info)
        state['release']=self.stage()
        return self.manager.apply(info,state,'fsr4')


class SteamTests(Fixture):
    def test_discovery_finds_external_library_with_spaces(self):
        info=steam.discover(self.home)
        self.assertEqual(info['game'],str(self.game))
        self.assertEqual(info['build'],'100')
        self.assertEqual(info['steam_config'],str(self.local))

    def test_missing_game_and_uninitialized_prefix(self):
        self.config.unlink()
        self.assertIsNone(steam.discover(self.home)['config'])
        with self.assertRaisesRegex(AddonError,'Launch PoE 2 once'):
            self.manager.require_game()
        (self.game/'PathOfExileSteam.exe').unlink()
        self.assertIsNone(steam.discover(self.home))

    def test_multiple_accounts_are_not_silently_overwritten(self):
        other=self.steam/'userdata/456/config/localconfig.vdf'
        other.parent.mkdir(parents=True);other.write_text(VDF)
        self.assertTrue(steam.discover(self.home)['account_ambiguous'])
        self.assertEqual(steam.discover(self.home,account='456')['steam_config'],str(other))

    def test_scoped_vdf_edits_preserve_nested_and_other_apps(self):
        value='WINEDLLOVERRIDES="dxgi=n,b" gamemoderun %command% --foo'
        changed=steam.launch_write(VDF,value)
        self.assertEqual(steam.launch_read(changed),value)
        self.assertIn('"nested" { "LaunchOptions" "keep nested" }',changed)
        self.assertIn('"123" { "LaunchOptions" "leave me alone" }',changed)
        self.assertIsNone(steam.launch_read(steam.launch_write(changed,None)))

    def test_override_merge_keeps_other_dlls_and_wrappers(self):
        current='WINEDLLOVERRIDES="dxgi,winmm=b;nvapi=n" gamemoderun %command% --arg'
        changed=steam.fsr4_launch(current)
        self.assertEqual(changed,'WINEDLLOVERRIDES="winmm=b;nvapi=n;dxgi=n,b" gamemoderun %command% --arg')
        self.assertEqual(steam.fsr4_launch(changed),changed)

    def test_display_changes_do_not_touch_other_preferences(self):
        data=steam.display_write(CONFIG,{'renderer_type':'DirectX12','upscale':'DLSS'})
        self.assertIn(b'texture_quality=Medium',data)
        self.assertIn(b'volume=42',data)
        self.assertEqual(steam.display_read(steam.display_write(data,steam.display_read(CONFIG))),steam.display_read(CONFIG))


class ManagerTests(Fixture):
    def test_legacy_managed_scalpel_requires_actual_pinned_bytes_to_launch(self):
        app = self.data / 'apps/Scalpel.AppImage'
        trusted = b'pinned build'
        other = b'legacy build'
        pin = dict(releases.PINS['scalpel'], size=len(trusted), sha256=digest(trusted))
        atomic(app, other, executable=True)
        atomic(self.data / 'scalpel.json', json_bytes(dict(pin, sha256=digest(other))))
        with patch.dict(releases.PINS, scalpel=pin), patch('poe2.manager.subprocess.Popen') as launch:
            self.assertFalse(self.manager.scalpel()['available'])
            # Even a stale locally cached hash must not authorize a launch.
            self.manager.hash_cache[str(app)]['sha256'] = pin['sha256']
            with self.assertRaisesRegex(AddonError, 'Reinstall'):
                self.manager.launch_scalpel(focus=True)
            launch.assert_not_called()
            atomic(app, trusted, executable=True)
            self.manager.launch_scalpel()
            self.assertEqual(launch.call_args.args[0][0], str(app))

    def test_changed_optiscaler_pin_blocks_launch_and_repair_but_allows_restore(self):
        self.install()
        with patch.dict(releases.PINS['optiscaler'], sha256='new-pin'):
            self.assertEqual(self.manager.status()['profile'], 'unpinned')
            with patch('poe2.manager.subprocess.Popen') as launch:
                with self.assertRaisesRegex(AddonError, 'pinned FSR4'):
                    self.manager.launch_game()
                launch.assert_not_called()
            with self.assertRaisesRegex(AddonError, 'plugin pin'):
                self.manager.repair()
            self.manager.switch('original')
            self.assertFalse((self.game / 'dxgi.dll').exists())
            with self.assertRaisesRegex(AddonError, 'plugin pin'):
                self.manager.switch('fsr4')

    def test_clean_install_and_restore_are_reversible(self):
        result=self.install()
        self.assertEqual(result['profile'],'fsr4')
        ini=(self.game/'OptiScaler.ini').read_text()
        self.assertIn('Fsr4EnableWatermark=false',ini)
        self.assertIn('Enabled=false',ini)
        self.assertIn('LogToFile=false',ini)
        self.manager.switch('original')
        self.assertFalse((self.game/'dxgi.dll').exists())
        self.assertEqual((self.game/'libxess.dll').read_bytes(),b'vanilla one')
        self.assertEqual(steam.display_read(self.config.read_bytes()),steam.display_read(CONFIG))
        self.assertEqual(steam.launch_read(self.local.read_text()),steam.launch_read(VDF))
        self.manager.switch('fsr4')
        self.assertEqual(self.manager.status()['profile'],'fsr4')

    def test_repair_fixes_spaced_ini_watermark_and_framegen_drift(self):
        self.install()
        ini=self.game/'OptiScaler.ini'
        text=ini.read_text().replace('Fsr4EnableWatermark=false','Fsr4EnableWatermark = auto').replace('Enabled=false','Enabled = auto')
        ini.write_text(text)
        self.assertEqual(self.manager.status()['profile'],'needs_repair')
        self.manager.repair()
        self.assertIn('Fsr4EnableWatermark=false',ini.read_text())
        self.assertIn('Enabled=false',ini.read_text())

    def test_new_game_build_keeps_new_vanilla_dll_when_restoring(self):
        self.install()
        self.build('101')
        (self.game/'libxess.dll').write_bytes(b'new Steam version')
        self.assertEqual(self.manager.status()['profile'],'needs_repair')
        self.manager.repair()
        self.manager.switch('original')
        self.assertEqual((self.game/'libxess.dll').read_bytes(),b'new Steam version')

    def test_updated_original_profile_repairs_offline_without_enabling_fsr4(self):
        self.install()
        self.manager.switch('original')
        self.build('101')
        self.assertEqual(self.manager.status()['profile'], 'needs_repair')
        with patch('poe2.releases.fetch', side_effect=AssertionError('Repair must not download')):
            with patch('poe2.steam.processes', return_value=['steam']):
                with self.assertRaisesRegex(AddonError, 'fully exit Steam'):
                    self.manager.repair()
            result = self.manager.repair()
        self.assertEqual(result['profile'], 'original')
        self.assertEqual(result['selected'], 'original')
        self.assertEqual(self.manager.state['build'], '101')
        self.assertFalse((self.game/'dxgi.dll').exists())
        self.assertEqual(steam.display_read(self.config.read_bytes()), steam.display_read(CONFIG))

    def test_missing_mod_file_is_repaired_without_a_download(self):
        self.install()
        (self.game/'amd_fidelityfx_upscaler_dx12.dll').unlink()
        with patch('poe2.releases.fetch',side_effect=AssertionError('Network not allowed')):
            self.manager.repair()
        self.assertEqual((self.game/'amd_fidelityfx_upscaler_dx12.dll').read_bytes(),b'fsr4')

    def test_unknown_changed_mod_is_not_silently_overwritten(self):
        self.install()
        (self.game/'dxgi.dll').write_bytes(b'another mod')
        with self.assertRaisesRegex(AddonError,'Unexpected change'):
            self.manager.repair()
        self.assertEqual((self.game/'dxgi.dll').read_bytes(),b'another mod')

    def test_release_rollback_removes_new_sdk_files_but_keeps_updated_game_baseline(self):
        self.install()
        previous=json.loads(self.manager.state_path.read_text())
        self.build('101');(self.game/'libxess.dll').write_bytes(b'new Steam version')
        info=self.manager.require_game()
        state=json.loads(self.manager.state_path.read_text())
        self.manager.reconcile(state,info)
        state['release']=self.stage('b',b'OptiScaler two')
        mapping=load(self.data/'payloads/b/files.json')
        mapping['new-sdk.dll']=self.manager.store.put(b'new optional SDK')
        atomic(self.data/'payloads/b/files.json',json_bytes(mapping))
        atomic(self.data/'rollback.json',json_bytes(previous))
        with patch.dict(releases.PINS['optiscaler'], sha256='b'):
            self.manager.apply(info,state,'fsr4')
            with self.assertRaisesRegex(AddonError, 'plugin pin'):
                self.manager.rollback()
        self.manager.rollback()
        self.assertEqual((self.game/'dxgi.dll').read_bytes(),b'OptiScaler one')
        self.assertFalse((self.game/'new-sdk.dll').exists())
        self.assertEqual(self.manager.status()['profile'],'fsr4')
        self.manager.switch('original')
        self.assertEqual((self.game/'libxess.dll').read_bytes(),b'new Steam version')

    def test_user_launch_option_changes_survive_repair_and_restore(self):
        self.install()
        text=self.local.read_text()
        options=steam.launch_read(text)+' --new-argument'
        self.local.write_text(steam.launch_write(text,options))
        self.manager.repair();self.manager.switch('original')
        self.assertEqual(steam.launch_read(self.local.read_text()),'gamemoderun %command% --foo --new-argument')

    def test_reset_requires_original_and_retains_backups(self):
        self.install()
        with self.assertRaisesRegex(AddonError,'Select Original'):
            self.manager.reset_setup()
        self.manager.switch('original');self.manager.reset_setup()
        self.assertFalse(self.manager.state_path.exists())
        self.assertEqual(len(list((self.data/'retired-installations').glob('*.json'))),1)
        self.assertEqual((self.game/'libxess.dll').read_bytes(),b'vanilla one')

    def test_process_guard_blocks_mutation(self):
        self.install()
        with patch('poe2.steam.processes',return_value=['steam']):
            with self.assertRaisesRegex(AddonError,'fully exit Steam'):
                self.manager.switch('original')
        self.assertTrue((self.game/'dxgi.dll').exists())

    def test_preferences_persist_across_switches(self):
        self.install()
        self.manager.configure({'quality':'Balanced','watermark':False})
        self.manager.switch('original');self.manager.switch('fsr4')
        self.assertEqual(steam.display_read(self.config.read_bytes())['upscale_quality'],'Balanced')
        self.assertIn('Fsr4EnableWatermark=false',(self.game/'OptiScaler.ini').read_text())

    def test_menu_shortcut_is_applied_and_persists_across_profiles(self):
        self.install()
        self.assertIn('ShortcutKey=0xDC', (self.game/'OptiScaler.ini').read_text())
        self.manager.configure({'menu_key': '0x79'})
        self.assertIn('ShortcutKey=0x79', (self.game/'OptiScaler.ini').read_text())
        manager = Manager(self.data, self.home)
        self.assertEqual(manager.preferences['menu_key'], '0x79')
        manager.switch('original')
        manager.switch('fsr4')
        self.assertIn('ShortcutKey=0x79', (self.game/'OptiScaler.ini').read_text())

    def test_menu_shortcut_change_is_blocked_while_steam_runs(self):
        self.install()
        before = (self.game/'OptiScaler.ini').read_bytes()
        with patch('poe2.steam.processes', return_value=['steam']):
            with self.assertRaises(AddonError):
                self.manager.configure({'menu_key': '0x79'})
        self.assertEqual((self.game/'OptiScaler.ini').read_bytes(), before)
        self.assertEqual(load(self.manager.preferences_path)['menu_key'], '0xDC')

    def test_invalid_shortcut_values_are_rejected_before_writes(self):
        self.install()
        before = (self.game/'OptiScaler.ini').read_bytes()
        for value in ['§', 'F10', '0x100', '0xGG']:
            with self.subTest(value=value), self.assertRaises(AddonError):
                self.manager.configure({'menu_key': value})
        self.assertEqual((self.game/'OptiScaler.ini').read_bytes(), before)
        self.assertEqual(load(self.manager.preferences_path)['menu_key'], '0xDC')

    def test_failed_write_rolls_back_files_and_registry(self):
        self.install()
        paths=[self.game/'dxgi.dll',self.game/'libxess.dll',self.config,self.local,self.manager.state_path]
        before={p:p.read_bytes() for p in paths}
        real=atomic;failed=False
        def fail_once(path,data,*args,**kwargs):
            nonlocal failed
            if path==self.config and not failed:
                failed=True;raise OSError('simulated disk error')
            return real(path,data,*args,**kwargs)
        with patch('poe2.storage.atomic',side_effect=fail_once):
            with self.assertRaises(OSError):self.manager.switch('original')
        self.assertEqual(before,{p:p.read_bytes() for p in paths})
        self.assertFalse((self.data/'transaction.json').exists())

    def test_crash_recovery_survives_a_new_process(self):
        store=self.manager.store
        file=self.root/'recover-me'
        file.write_bytes(b'original')
        entry={'path':str(file),'before':store.put(b'original')}
        atomic(self.data/'transaction.json',json_bytes([entry]));file.write_bytes(b'partial write')
        Manager(self.data,self.home).prepare()
        self.assertEqual(file.read_bytes(),b'original')

    def test_template_schema_change_fails_before_mutating_game(self):
        with self.assertRaisesRegex(AddonError,'unsupported configuration schema'):
            optiscaler.configure(b'[Unknown]\nfoo=bar',self.manager.preferences)
        self.assertFalse((self.game/'dxgi.dll').exists())

    def test_trade_and_app_commands_do_not_execute_a_shell(self):
        self.install()
        with patch('poe2.manager.subprocess.Popen') as launch,patch('poe2.manager.shutil.which',return_value='/usr/bin/scalpel-poe'):
            with patch.object(self.manager,'scalpel',return_value={'available':True,'path':'/usr/bin/scalpel-poe'}):
                self.manager.launch_scalpel()
            args,kwargs=launch.call_args
            self.assertEqual(args[0],['/usr/bin/scalpel-poe','--ozone-platform=x11'])
            self.assertEqual(kwargs['env']['XDG_SESSION_TYPE'],'x11')
            self.assertNotIn('shell',kwargs)


class ScalpelTests(Fixture):
    def setUp(self):
        super().setUp()
        self.scalpel_info = patch.object(self.manager, 'scalpel', return_value={
            'available': True, 'path': '/usr/bin/scalpel-poe', 'version': 'test'})
        self.scalpel_info.start()
        self.addCleanup(self.scalpel_info.stop)

    def settings(self, data):
        atomic(self.manager.scalpel_config(), json_bytes(data))

    def test_status_requires_actual_onboarding_and_poe2(self):
        self.assertEqual(self.manager.status()['scalpel']['setup'], 'required')
        for config, expected in [
            ({'poeVersion': 2}, 'required'),
            ({'onboardingCompleted': False, 'poeVersion': 2}, 'required'),
            ({'onboardingCompleted': True, 'poeVersion': 1}, 'wrong_game'),
            ({'onboardingCompleted': True, 'poeVersion': '2'}, 'wrong_game'),
            ({'onboardingCompleted': True, 'poeVersion': 2}, 'ready'),
        ]:
            with self.subTest(config=config):
                self.settings(config)
                self.assertEqual(self.manager.status()['scalpel']['setup'], expected)

    def test_first_play_opens_only_scalpel_and_does_not_claim_setup_complete(self):
        with patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
            message = self.manager.launch_game()
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(launch.call_args.args[0], ['/usr/bin/scalpel-poe', '--ozone-platform=x11'])
        self.assertIn('game has not been launched', message)
        self.assertEqual(load(self.manager.scalpel_config()), {
            'poeVersion': 2, 'onboardingSelectedGames': {'poe1': False, 'poe2': True}})
        self.assertEqual(self.manager.scalpel_setup(), 'required')

    def test_incomplete_and_wrong_game_settings_are_preserved_and_block_game(self):
        for config in [
            {'onboardingCompleted': False, 'poeVersion': 2, 'onboardingStep': 'trade'},
            {'onboardingCompleted': True, 'poeVersion': 1, 'hotkey': 'Ctrl+D'},
        ]:
            with self.subTest(config=config):
                self.settings(config)
                before = self.manager.scalpel_config().read_bytes()
                with patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
                    self.manager.launch_game()
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0][0], '/usr/bin/scalpel-poe')
                self.assertEqual(self.manager.scalpel_config().read_bytes(), before)

    def test_unreadable_settings_do_not_break_status_or_get_overwritten(self):
        for raw in [b'{unfinished', b'[]', b'null', b'\xff', b'x' * (4 * 1024 * 1024 + 1)]:
            with self.subTest(raw=raw[:20]):
                atomic(self.manager.scalpel_config(), raw)
                self.assertEqual(self.manager.status()['scalpel']['setup'], 'unknown')
                with patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
                    self.manager.launch_game()
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0][0], '/usr/bin/scalpel-poe')
                self.assertEqual(self.manager.scalpel_config().read_bytes(), raw)

    def test_completed_setup_starts_scalpel_before_steam(self):
        self.settings({'onboardingCompleted': True, 'poeVersion': 2})
        with patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
            self.manager.launch_game()
        self.assertEqual([c.args[0] for c in launch.call_args_list], [
            ['/usr/bin/scalpel-poe', '--ozone-platform=x11'], ['steam', '-applaunch', steam.APPID]])

    def test_running_completed_scalpel_is_not_started_twice(self):
        self.settings({'onboardingCompleted': True, 'poeVersion': 2})
        with patch('poe2.steam.processes', return_value=['scalpel']), patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
            self.manager.launch_game()
        launch.assert_called_once_with(['steam', '-applaunch', steam.APPID],
                                      stdout=-3, stderr=-3, start_new_session=True)

    def test_running_incomplete_scalpel_can_be_raised_for_setup(self):
        self.settings({'onboardingCompleted': False, 'poeVersion': 2})
        with patch('poe2.steam.processes', return_value=['scalpel']), patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
            self.manager.launch_game()
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(launch.call_args.args[0][0], '/usr/bin/scalpel-poe')

    def test_scalpel_remains_optional(self):
        for available, automatic in [(False, True), (True, False)]:
            with self.subTest(available=available, automatic=automatic):
                self.manager.preferences['auto_scalpel'] = automatic
                with patch.object(self.manager, 'scalpel', return_value={'available': available}), patch('poe2.manager.subprocess.Popen') as launch, patch('poe2.manager.shutil.which', return_value='/usr/bin/steam'):
                    self.manager.launch_game()
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(launch.call_args.args[0], ['steam', '-applaunch', steam.APPID])
                self.assertFalse(self.manager.scalpel_config().exists())

    def test_launch_uses_xdg_config_home(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'alternate-config')}):
            with patch('poe2.manager.subprocess.Popen'):
                self.manager.launch_scalpel()
            self.assertTrue((self.root / 'alternate-config/scalpel/config.json').exists())
        self.assertFalse((self.home / '.config/scalpel/config.json').exists())


class NetworkTests(unittest.TestCase):
    def test_url_validation_blocks_other_repositories(self):
        for url in ['http://github.com/optiscaler/OptiScaler/releases/download/v1/a.7z','https://evil.example/a','https://github.com/other/repo/releases/download/v1/a.7z']:
            with self.assertRaises(AddonError):releases.validate_url(url,'optiscaler/OptiScaler')

    def test_new_upstream_metadata_cannot_authorize_replacement_bytes(self):
        original = b'a' * 5000
        replacement = b'b' * len(original)
        for component, repo in releases.REPOS.items():
            with self.subTest(component=component), tempfile.TemporaryDirectory() as temp:
                pin = dict(releases.PINS[component], size=len(original), sha256=digest(original))
                url = f"https://github.com/{repo}/releases/download/{pin['tag']}/{pin['name']}"
                metadata = {'tag_name': 'v99.0.0', 'assets': [{
                    'name': pin['name'], 'browser_download_url': url,
                    'size': len(replacement), 'digest': 'sha256:' + digest(replacement),
                }]}

                def fetch(request_url, limit, destination=None):
                    if destination is None:
                        self.assertEqual(request_url, f'https://api.github.com/repos/{repo}/releases/latest')
                        return json.dumps(metadata).encode()
                    self.assertEqual(request_url, url)
                    return destination.write_bytes(replacement)

                with patch.dict(releases.PINS, {component: pin}), patch.object(releases, 'fetch', side_effect=fetch) as network:
                    self.assertEqual(releases.latest_tag(component), 'v99.0.0')
                    network.reset_mock()
                    with self.assertRaisesRegex(AddonError, 'release pin'):
                        releases.download(component, Path(temp))
                    self.assertEqual(network.call_count, 1)
                    self.assertEqual(list(Path(temp).iterdir()), [])

    def test_offline_cache_requires_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            data = b'a' * 5000
            pin = dict(releases.PINS['scalpel'], size=len(data), sha256=digest(data))
            cache = Path(temp)
            asset = cache / (pin['sha256'] + '-' + pin['name'])
            asset.write_bytes(data)
            with patch.dict(releases.PINS, scalpel=pin), patch.object(releases, 'fetch', side_effect=AddonError('offline')) as network:
                selected, path = releases.download('scalpel', cache)
                self.assertEqual(selected['tag'], pin['tag'])
                self.assertEqual(path, asset)
                network.assert_not_called()
                asset.write_bytes(b'b' * len(data))
                with self.assertRaisesRegex(AddonError, 'offline'):
                    releases.download('scalpel', cache)

    def test_archive_path_traversal_is_rejected(self):
        result=type('Result',(),{'stdout':b'../escape.dll\n'})()
        with tempfile.TemporaryDirectory() as temp,patch('poe2.releases.shutil.which',return_value='/usr/bin/bsdtar'),patch('poe2.releases.subprocess.run',return_value=result):
            with self.assertRaisesRegex(AddonError,'unsafe path'):
                releases.extract(Path('release.7z'),Path(temp)/'out')


class UiTests(unittest.TestCase):
    def test_dynamic_markup_never_reaches_rich_text_or_tooltips(self):
        root=Path(__file__).resolve().parents[1]
        qml=(root/'Panel.qml').read_text();plain=(root/'PlainText.qml').read_text()
        self.assertIn('textFormat: Text.PlainText',plain)
        self.assertNotRegex(qml,r'(?m)^\s*Text\s*\{')
        self.assertIn('tooltipText: ""',qml)
        self.assertIn('String(result.error',qml)
        self.assertIn('text: root.message',qml)
        self.assertNotIn('execDetached',qml)


if __name__=='__main__':unittest.main()
