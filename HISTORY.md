# VS Code Launcher version history

## v0.14.0 30 October 2026

- Add Google Antigravity as a third launch target (N/I/A keys). Antigravity
  is detected automatically from the Windows registry or default install
  locations; WSL workspaces are opened through Antigravity's built-in
  remote-WSL support using the default WSL distro. Optional
  `windows_antigravity_command` and `wsl_antigravity_command` overrides in
  `config.json`.

## v0.13.0 3 July 2026

- Improve tab/shift-tab cycling and add cursor key navigation.

## v0.12.2 6 June 2025

- Fix bug with compiled program not correctly saving window size changes.

## v0.12.1 23 May 2025

- Fix shift-TAB navigation (using Win32 `GetKeyState` API)

## v0.12.0 23 May 2025

- Save and restore window size.

## v0.11.0 22 May 2025

- Make VSCL single-instance.

## v0.10.0 21 May 2025

- Add support for choosing between standard VS Code and VS Code Insiders.
  Remember the last choice.
- Allow exiting with the ESCAPE key.
- Use constants for initial window height/width.
- Add more logging.
- Avoid path traversal issues.

## v0.9.0 19 May 2025

First public release.
