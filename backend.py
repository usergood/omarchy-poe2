#!/usr/bin/env python3
"""JSON CLI used by the Omarchy widget. No shell interpolation of user input."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from poe2.manager import Manager, TRADE_URL
from poe2.storage import AddonError
from poe2 import steam


def run(argv=None):
    parser = argparse.ArgumentParser(description='Omarchy PoE 2 addon')
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ['status', 'original', 'fsr4', 'repair', 'install-optiscaler', 'rollback', 'check-updates',
                 'install-scalpel', 'install-pob-redux', 'launch', 'launch-scalpel', 'launch-pob-redux',
                 'trade', 'exit-steam', 'install-game', 'recover', 'reset-setup']:
        sub.add_parser(name)
    config = sub.add_parser('configure')
    config.add_argument('--quality', choices=['Quality', 'Balanced', 'Performance'])
    config.add_argument('--menu-key')
    config.add_argument('--steam-root')
    config.add_argument('--account')
    for name in ['watermark', 'diagnostics', 'auto-scalpel']:
        config.add_argument('--' + name, choices=['on', 'off'])
    args = parser.parse_args(argv)
    manager = Manager()
    # Status never races an active write: the UI retains its last result on busy.
    with (manager.root / 'lock').open('a') as lock:
        operation = fcntl.LOCK_SH if args.action == 'status' else fcntl.LOCK_EX
        deadline = time.monotonic() + 3
        while True:
            try:
                fcntl.flock(lock, operation | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if args.action == 'status':
                    return {'ok': True, 'busy': True}
                if time.monotonic() >= deadline:
                    raise AddonError('Another addon operation is still running.') from exc
                time.sleep(0.05)
        action = args.action
        message = ''
        if action == 'status':
            return manager.status()
        if action in {'original', 'fsr4'}:
            result = manager.switch(action)
            result['message'] = 'Profile applied. Start PoE 2 to use it.'
            return result
        methods = {'repair': manager.repair, 'install-optiscaler': manager.install_optiscaler,
                   'rollback': manager.rollback, 'check-updates': manager.check_updates,
                   'install-scalpel': manager.install_scalpel, 'install-pob-redux': manager.install_pob_redux,
                   'reset-setup': manager.reset_setup}
        if action in methods:
            result = methods[action]()
            result['message'] = {'repair': 'Your saved settings and game integration have been reapplied.',
                                 'install-optiscaler': 'Official OptiScaler installed; FSR4 is selected.',
                                 'rollback': 'The previous OptiScaler version has been restored.',
                                 'check-updates': 'Update checks finished.',
                                 'install-scalpel': 'Verified Scalpel AppImage installed for your user.',
                                 'install-pob-redux': 'Verified PoB Redux AppImage installed for your user.',
                                 'reset-setup': 'Setup registry reset; original backups have been retained.'}[action]
            return result
        if action == 'configure':
            changes = {k: v for k, v in vars(args).items() if k != 'action' and v is not None}
            for key in ['watermark', 'diagnostics', 'auto_scalpel']:
                if key in changes:
                    changes[key] = changes[key] == 'on'
            result = manager.configure(changes)
            result['message'] = 'Preferences saved.'
            return result
        if action == 'launch':
            message = manager.launch_game()
        elif action == 'launch-scalpel':
            message = manager.launch_scalpel(focus=True)
        elif action == 'launch-pob-redux':
            message = manager.launch_pob_redux()
        elif action == 'exit-steam':
            if 'game' in steam.processes():
                raise AddonError('Exit PoE 2 before asking Steam to shut down.')
            if not shutil.which('steam'):
                raise AddonError('Native Steam is not installed.')
            subprocess.Popen(['steam', '-shutdown'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            message = 'Steam shutdown requested. Wait until it exits before switching profiles.'
        elif action in {'trade', 'install-game'}:
            if not shutil.which('xdg-open'):
                raise AddonError('xdg-open is missing. Install xdg-utils to use browser and Steam links.')
            url = TRADE_URL if action == 'trade' else 'steam://install/' + steam.APPID
            subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            message = 'Opened the trade site in your default browser.' if action == 'trade' else 'Opened PoE 2 installation in Steam.'
        elif action == 'recover':
            manager.prepare()
            message = 'Interrupted changes recovered.'
        result = manager.status()
        result['message'] = message
        return result


def main():
    try:
        print(json.dumps(run(), ensure_ascii=False))
    except Exception as exc:
        # Errors are rendered only in a Text.PlainText sink. Never dump configs/tokens.
        text = str(exc)[:400] if isinstance(exc, (AddonError, OSError, ValueError)) else 'Unexpected addon error. Run the test suite or report the operation that failed.'
        print(json.dumps({'ok': False, 'error': text}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
