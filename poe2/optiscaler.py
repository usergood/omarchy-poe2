"""Explicit, version-aware FSR4 configuration; never recapture drifted defaults."""
import configparser
import io
import re

from .storage import AddonError


def configure(defaults, preferences, previous=None):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read_string(defaults.decode('utf-8-sig'))
    if previous:
        old = configparser.ConfigParser(interpolation=None, strict=False)
        old.optionxform = str
        try:
            old.read_string(previous.decode('utf-8-sig'))
            for section in parser.sections():
                if old.has_section(section):
                    values = {k.lower(): v for k, v in old[section].items()}
                    for key in parser[section]:
                        if key.lower() in values:
                            parser[section][key] = values[key.lower()]
        except (UnicodeError, configparser.Error):
            pass
    def setting(section, name, value, required=True):
        if not parser.has_section(section):
            raise AddonError('This OptiScaler release has an unsupported configuration schema.')
        key = next((k for k in parser[section] if k.lower() == name.lower()), None)
        if key is None:
            if required:
                raise AddonError('This OptiScaler release changed ' + name + '. Update the addon before installing it.')
            return
        parser[section][key] = value
    # The known stable SDK route supports INT8 on the user's RDNA2 card.
    # Future schema changes fail before any game file is touched.
    setting('Upscalers', 'Dx12Upscaler', 'fsr31')
    setting('FSR', 'UpscalerIndex', '0')
    setting('FSR', 'Fsr4Update', 'false')
    setting('FSR', 'Fsr4ForceEnableInt8', 'true')
    setting('FSR', 'Fsr4EnableWatermark', 'true' if preferences['watermark'] else 'false')
    setting('FSR', 'Fsr4EnableDebugView', 'false', False)
    setting('FrameGen', 'Enabled', 'false')
    setting('FrameGen', 'FGInput', 'nofg')
    setting('FrameGen', 'FGOutput', 'nofg')
    setting('Spoofing', 'Dxgi', 'false')
    setting('Menu', 'ShortcutKey', preferences['menu_key'])
    # Info only on demand; tracing per frame can itself distort performance.
    setting('Log', 'LogToFile', 'true' if preferences['diagnostics'] else 'false')
    setting('Log', 'LogLevel', '2')
    buffer = io.StringIO()
    parser.write(buffer, space_around_delimiters=False)
    return buffer.getvalue().encode()


def validate_preferences(preferences):
    if preferences.get('quality') not in {'Quality', 'Balanced', 'Performance'}:
        raise AddonError('Choose Quality, Balanced, or Performance.')
    if not re.fullmatch(r'0x[0-9a-fA-F]{1,2}', str(preferences.get('menu_key', ''))):
        raise AddonError('The menu key must be a Windows virtual key code, for example 0xDC for § on Swedish keyboards.')
    for key in ['watermark', 'diagnostics', 'auto_scalpel']:
        if type(preferences.get(key)) is not bool:
            raise AddonError('Invalid boolean preference: ' + key)
