"""
Native OS file/folder dialog support.

Attempts to open a native folder picker on Linux, macOS, and Windows.
Falls back gracefully when no GUI toolkit is available (e.g. headless server).
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_native_folder_dialog(
    initial_dir: str | None = None,
) -> str | None:
    """
    Open the native OS folder picker dialog.

    Returns the selected folder path, or ``None`` if cancelled / unavailable.

    Tries, in order:

    1. **tkinter** ``filedialog.askdirectory()``
    2. **zenity** — GNOME / GTK-based Linux
    3. **kdialog** — KDE Linux
    4. **osascript** — macOS
    5. **powershell** — Windows
    """
    # In test mode we prefer a headless preset path to avoid GUI dialog popups.
    test_folder = os.environ.get("MORPHIC_TEST_FOLDER")
    if test_folder and os.path.isdir(test_folder):
        return test_folder

    if os.environ.get("PYTEST_CURRENT_TEST"):
        asset_folder = Path(__file__).resolve().parents[2] / "assets" / "test"
        if asset_folder.exists():
            return str(asset_folder)

    initial_dir = initial_dir or str(os.path.expanduser("~"))

    result = _try_tkinter(initial_dir)
    if result is not None:
        return result

    system = platform.system()

    if system == "Linux":
        result = _try_zenity(initial_dir)
        if result is not None:
            return result
        result = _try_kdialog(initial_dir)
        if result is not None:
            return result

    if system == "Darwin":
        result = _try_osascript(initial_dir)
        if result is not None:
            return result

    if system == "Windows":
        result = _try_powershell(initial_dir)
        if result is not None:
            return result

    logger.debug("No native folder dialog available on this system")
    return None


# ── Backend implementations ────────────────────────────────────────────────


def _try_tkinter(initial_dir: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select folder to scan",
        )
        root.destroy()
        return folder if folder else None
    except Exception as exc:
        logger.debug("tkinter dialog failed: %s", exc)
        return None


def _try_zenity(initial_dir: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "zenity",
                "--file-selection",
                "--directory",
                f"--filename={initial_dir}/",
                "--title=Select folder to scan",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _try_kdialog(initial_dir: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "kdialog",
                "--getexistingdirectory",
                initial_dir,
                "--title",
                "Select folder to scan",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _try_osascript(initial_dir: str) -> str | None:
    try:
        script = (
            f'set defaultDir to POSIX file "{initial_dir}"\n'
            f"set chosenDir to choose folder with prompt "
            f'"Select folder to scan" default location defaultDir\n'
            f"return POSIX path of chosenDir"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().rstrip("/")
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _try_powershell(initial_dir: str) -> str | None:
    try:
        script = (
            "[System.Reflection.Assembly]::LoadWithPartialName("
            "'System.Windows.Forms') | Out-Null; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$dialog.SelectedPath = '{initial_dir}'; "
            "$dialog.Description = 'Select folder to scan'; "
            "if ($dialog.ShowDialog() -eq 'OK') "
            "{ $dialog.SelectedPath }"
        )
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
