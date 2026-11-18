# Changelog

## 1.2.1

- Pin the exact OptiScaler archive and Scalpel AppImage to their SHA-256 digests and sizes. Tool installs and updates reject replacement binaries.
- Show the installable version separately from the latest upstream release in Tools.

## 1.2.0

- Install and develop through the Omarchy plugin manager. Retire the separate local installer.
- Jump from Play to Scalpel setup, see install and update actions for each tool, and expand diagnostics when needed.
- Add illustrated covers, refreshed widget screenshots, and a visual guide to repair after Steam updates.

## 1.1.1

- Confirm before installing or updating FSR4. The panel explains which game files and settings the operation changes and how to restore the Original profile.
- Document dependencies, license, and removal steps, and add a Play screenshot for the Omarchy Plugin Marketplace.

## 1.1.0

- Use the same neutral theme surface for the PoE 2 and Scalpel cards instead of tinting the game card with the accent color.
- Simplify the user guide, add screenshots of the current interface and move advanced details into a technical reference.
- Align button and switch text with the popup palette, improve switch description contrast on light themes, and test live palette changes.
- Put step-by-step repair guidance and the next action directly in the Play game card, including exiting Steam and repairing the selected profile.
- Record an OptiScaler menu shortcut by pressing a key, reviewing it, and explicitly accepting or cancelling; retain the Swedish § default.
- Keep panel navigation and feedback fixed, fit content to the available screen height, and reserve a gutter when page scrolling is needed.
- Redesign Play, Tools and Settings with a branded header, theme-aware cards and clearer typography.
- Show live PoE 2, Scalpel and Steam states without dimming controls during background status checks.
- Guide first-time Scalpel onboarding before launching PoE 2 with automatic Scalpel startup.
- Detect completed setup and the selected game without changing existing Scalpel preferences.
- Respect XDG_CONFIG_HOME for Scalpel settings and allow reopening its running window.
- Replace the generic gamepad with a custom gold waystone II icon, included in local installs.

## 1.0.0

- Unified Play, Tools and Settings pages for Steam PoE 2, Scalpel and the trade site.
- Portable native Steam library/account discovery and guided first-run prerequisites.
- Official stable OptiScaler and Scalpel downloads with SHA-256 verification.
- Persistent FSR4 preferences: watermark off, frame generation off, § menu key and no trace logging.
- Quality/Balanced/Performance selection without modifying the original graphics profile.
- Build-aware Steam repair, immutable backups, transactional writes, crash recovery and release rollback.
- Existing Scalpel package support plus optional user-owned AppImage updates.
- Manual update checks; no background network polling.
