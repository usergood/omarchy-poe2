# Omarchy PoE 2

Launch Path of Exile 2, open trade, and manage your companion tools from the Omarchy bar.

- **Play** — launch PoE 2, see which apps are running, and open the official trade site.
- **Scalpel** — optional item price checks and an in-game companion overlay.
- **FSR4** — optional graphics upscaling, with an easy switch back to your original setup.
- **Repair** — guided steps to get your selected profile ready after a game update.

## A look inside

The panel follows your Omarchy theme and font. Click a screenshot to view it at full size.

| Play | Tools | Settings |
| --- | --- | --- |
| [![Play: game, companion and rendering controls](docs/screenshots/play.png)](docs/screenshots/play.png) | [![Tools: installations, repair and updates](docs/screenshots/tools.png)](docs/screenshots/tools.png) | [![Settings: startup, image quality and menu shortcut](docs/screenshots/settings.png)](docs/screenshots/settings.png) |

<details>
<summary>Prefer a light theme? See Catppuccin Latte.</summary>

![Settings using the Catppuccin Latte theme](docs/screenshots/settings-light.png)

</details>

## Before you start

You need an up-to-date Omarchy installation with plugin support, Steam, and a copy
of PoE 2 installed through Steam. Flatpak Steam is not supported.

Launch PoE 2 once from Steam, then close the game. This creates the settings the
plugin needs.

**FSR4 is optional.** This plugin's preset targets AMD RDNA2/3 graphics cards; other
GPUs are not validated. You can use the launcher, trade shortcut and Scalpel without
setting up FSR4. See [compatibility details](docs/technical-reference.md#compatibility-and-dependencies)
if you are unsure.

## Install

Open a terminal and run:

```bash
omarchy plugin add https://github.com/usergood/omarchy-poe2 --enable --yes
```

Look for the **gold II emblem** on the right side of your bar. Click it to open the
plugin. Installing the plugin does not change your game files.

## Start playing

Open **Play** and choose **Launch PoE 2**. The cards show whether PoE 2 and Scalpel
are running, and the Steam badge shows whether Steam is open.

**Open trade** opens the official PoE 2 trade site in your browser.

### Add Scalpel for price checks

1. Open **Tools** and choose **Install / Update Scalpel AppImage**, or use your existing Scalpel installation.
2. Return to **Play** and choose **Open Scalpel setup**.
3. Complete Scalpel's setup and select **PoE 2**. Let it restart if it asks.
4. Return to the plugin and launch the game.

By default, the plugin starts Scalpel with PoE 2. If Scalpel still needs setup,
it opens Scalpel first and waits for you to finish. Click **Launch PoE 2** again
when you are ready. You can turn automatic startup off under **Settings**.

### Try FSR4 upscaling

1. In Steam, open PoE 2's **Properties → Compatibility** and select a recent GE-Proton or Proton Experimental.
2. Close PoE 2 and fully exit Steam.
3. Open **Tools → Install / Update FSR4**. This installs OptiScaler, which provides the FSR4 integration.
4. Return to **Play** and launch PoE 2.

Use **Original** or **FSR4** under **Rendering profile** to switch between them.
Close the game and Steam before switching. **Original** restores the game setup
saved before FSR4 was installed.

Under **Settings**, try **Quality**, **Balanced** or **Performance** to find what
works best on your PC. FSR4 is not guaranteed to improve performance.

## After a game update

If the game card says **Profile needs repair**, follow the steps shown there:

1. Close PoE 2 if it is running.
2. Click **Exit Steam to repair** and wait for the **Steam closed** badge.
3. Click **Repair Original profile** or **Repair FSR4 profile**, depending on your selection.
4. When repair finishes, click **Launch PoE 2**.

Repair uses saved files without downloading them again. It keeps your selected
profile and preferences. It does not switch you from Original to FSR4.

## Make it yours

Open **Settings** to change automatic Scalpel startup, FSR4 image quality, the
verification watermark, or diagnostic logging.

To change the OptiScaler menu shortcut:

1. Close PoE 2 and Steam.
2. Find **Diagnostics & Hotkeys → Menu shortcut** and click **Change**.
3. Press a key, then choose **Accept key**. Use **Try another** or **Cancel** if needed.

The default is **§ on a Swedish keyboard**. Single keys such as F10 are supported;
Esc cancels recording. The new shortcut applies the next time you launch the game.

## Updates and common questions

- **Update the plugin:** use Omarchy's plugin manager.
- **Update Scalpel or FSR4:** use the install/update buttons under **Tools**. **Check updates** checks those tools, not the plugin itself.
- **Old icon or layout after updating?** Run `omarchy restart shell` once.
- **Game not found?** Check that PoE 2 is installed in regular Steam, then launch it once from Steam.
- **Buttons are dimmed?** Fully exit PoE 2 and Steam before changing graphics settings, shortcuts or profiles.
- **Scalpel is open but price checking does not work?** Finish its setup, check that PoE 2 is selected, and review its hotkeys. See [troubleshooting](docs/technical-reference.md#troubleshooting-and-safety) for more help.

## Remove the plugin

First close PoE 2 and Steam, then select **Original** to restore the game setup.
After that, remove the plugin:

```bash
omarchy plugin remove usergood.poe2 --yes
```

For advanced settings, local installation, compatibility and developer checks,
see the [technical reference](docs/technical-reference.md).

This is an independent community plugin. PoE 2, [Scalpel](https://github.com/scalpelpoe/scalpel)
and [OptiScaler](https://github.com/optiscaler/OptiScaler) are separate projects.
FSR4 uses a third-party game modification; review the upstream compatibility and usage notes before enabling it.
