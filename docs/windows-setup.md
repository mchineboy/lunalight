# Lunalight on Windows

This guide gets a Windows PC ready to edit Lunalight's BASIC source, build the
canonical bank-2 game, and play it. It uses WSL2 (Ubuntu on Windows) for the
build tools and the normal Windows VICE app for playing the finished game.

## What Dad needs

- A 64-bit Windows 10 (version 2004 or later) or Windows 11 PC.
- An internet connection for the one-time installs.
- About 30 minutes the first time.

The project folder should live in Linux (`/home/...`), not under `C:\`, because
the build tools run inside WSL2.

## 1. Install Ubuntu (WSL2)

Open **PowerShell as Administrator**, run this command, then restart Windows
when it asks:

```powershell
wsl --install
```

Open **Ubuntu** from the Start menu. The first launch asks for a Linux user name
and password; write the password down, because Ubuntu will ask for it when
installing tools.

## 2. Install the build tools

In the Ubuntu window, paste these commands one at a time:

```bash
sudo apt update
sudo apt install -y build-essential git python3 cc65 vice xvfb
git clone https://github.com/mchineboy/lunalight.git ~/lunalight
cd ~/lunalight
```

Check that the important programs were installed:

```bash
command -v make petcat x64sc c1541 ca65 ld65
```

That command should print six paths. If it does, make the canonical game:

```bash
xvfb-run -a make
```

The playable result is `build/lunalight-blitz-full.prg`. Do not try to play
`build/lunalight.prg`: that is the readable BASIC source used by the compiler,
not a complete game image.

## 3. Install VICE for Windows

Download the 64-bit GTK3 Windows build of VICE from the official
[VICE Windows download page](https://vice-emu.sourceforge.io/windows.html),
unzip it, and run `x64sc.exe` once.

From Ubuntu, open the finished build folder in Windows Explorer:

```bash
cd ~/lunalight
explorer.exe build
```

In that Explorer window, start `lunalight-blitz-full.prg` from VICE with
**File → Autostart disk/tape image**. The included
`lunalight.d64` is an alternative disk image; in VICE use **File → Attach disk
image**, then type `LOAD"*",8,1` and `RUN`.

## 4. Install and use Cursor

Download and install the Windows edition of
[Cursor](https://www.cursor.com/downloads). In Cursor, install its WSL support,
then open the project from Ubuntu with:

```bash
cd ~/lunalight
cursor .
```

If `cursor` is not recognized, open Cursor normally, use the Remote/WSL command
to connect to Ubuntu, and open `/home/<your-linux-name>/lunalight`. Use Cursor's
regular **Editor Window** for WSL projects; if both Cursor's WSL extension and
Microsoft's old Remote - WSL extension are installed, disable the Microsoft one
to avoid a conflict.

The source to edit is:

```text
src/lunalight.bas
```

Use lower-case BASIC source. Do not edit anything in `build/`; the next build
recreates that folder. Before asking Cursor to make a game change, have it read
`AGENTS.md` and `docs/feature-layering.md` first. A useful first prompt is:

```text
Read AGENTS.md and docs/feature-layering.md. Explain how src/lunalight.bas
starts a round, but do not edit any files.
```

After a small source edit, build and test in Cursor's Ubuntu terminal:

```bash
xvfb-run -a make
xvfb-run -a make verify-blitz-gameplay
```

Never use `make -j`: the VICE-driven checks must run one at a time.

## If something goes wrong

| Symptom | What to do |
| --- | --- |
| `wsl --install` fails | Run Windows Update, restart, and try again. On older Windows, follow Microsoft's [manual WSL setup](https://learn.microsoft.com/windows/wsl/install-manual). |
| `x64sc` or `petcat` is missing | Run `sudo apt install -y vice` again. |
| `ca65` is missing | Run `sudo apt install -y cc65` again. |
| Cursor opens a Windows terminal instead of Ubuntu | Reopen the folder through Cursor's WSL/Remote connection, or run `cursor .` from the Ubuntu terminal. |
| The game says `OUT OF MEMORY` immediately | It is almost certainly the bare `lunalight.prg`; play `lunalight-blitz-full.prg` or `lunalight.d64` instead. |

For WSL installation details, see Microsoft's [WSL install guide](https://learn.microsoft.com/windows/wsl/install).
