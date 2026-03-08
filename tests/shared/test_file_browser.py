"""Tests for morphic.shared.file_browser — all fallback paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from morphic.shared.file_browser import (
    _try_kdialog,
    _try_osascript,
    _try_powershell,
    _try_tkinter,
    _try_zenity,
    open_native_folder_dialog,
)


class TestTryTkinter:
    @patch("tkinter.filedialog.askdirectory", return_value="/selected/folder")
    @patch("tkinter.Tk")
    def test_success(self, mock_tk_cls, mock_askdir) -> None:
        mock_root = MagicMock()
        mock_tk_cls.return_value = mock_root

        result = _try_tkinter("/home/user")
        assert result == "/selected/folder"

    @patch("tkinter.filedialog.askdirectory", return_value="")
    @patch("tkinter.Tk")
    def test_cancelled(self, mock_tk_cls, mock_askdir) -> None:
        mock_root = MagicMock()
        mock_tk_cls.return_value = mock_root

        result = _try_tkinter("/home/user")
        assert result is None

    @patch("builtins.__import__", side_effect=ImportError("No tkinter"))
    def test_import_error(self, mock_import) -> None:
        result = _try_tkinter("/home/user")
        assert result is None


class TestTryZenity:
    @patch("morphic.shared.file_browser.subprocess.run")
    def test_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/selected/folder\n",
        )
        result = _try_zenity("/home/user")
        assert result == "/selected/folder"

    @patch("morphic.shared.file_browser.subprocess.run")
    def test_cancelled(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = _try_zenity("/home/user")
        assert result is None

    @patch(
        "morphic.shared.file_browser.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_not_found(self, mock_run) -> None:
        result = _try_zenity("/home/user")
        assert result is None


class TestTryKdialog:
    @patch("morphic.shared.file_browser.subprocess.run")
    def test_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/selected/folder\n",
        )
        result = _try_kdialog("/home/user")
        assert result == "/selected/folder"

    @patch("morphic.shared.file_browser.subprocess.run")
    def test_cancelled(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = _try_kdialog("/home/user")
        assert result is None

    @patch(
        "morphic.shared.file_browser.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_not_found(self, mock_run) -> None:
        result = _try_kdialog("/home/user")
        assert result is None


class TestTryOsascript:
    @patch("morphic.shared.file_browser.subprocess.run")
    def test_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/Users/test/folder/\n",
        )
        result = _try_osascript("/Users/test")
        assert result == "/Users/test/folder"

    @patch("morphic.shared.file_browser.subprocess.run")
    def test_cancelled(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = _try_osascript("/Users/test")
        assert result is None

    @patch(
        "morphic.shared.file_browser.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_not_found(self, mock_run) -> None:
        result = _try_osascript("/Users/test")
        assert result is None


class TestTryPowershell:
    @patch("morphic.shared.file_browser.subprocess.run")
    def test_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="C:\\Users\\test\\folder\n",
        )
        result = _try_powershell("C:\\Users\\test")
        assert result == "C:\\Users\\test\\folder"

    @patch("morphic.shared.file_browser.subprocess.run")
    def test_cancelled(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = _try_powershell("C:\\Users\\test")
        assert result is None

    @patch(
        "morphic.shared.file_browser.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_not_found(self, mock_run) -> None:
        result = _try_powershell("C:\\Users\\test")
        assert result is None


class TestOpenNativeFolderDialog:
    @patch("morphic.shared.file_browser._try_tkinter", return_value="/chosen")
    def test_tkinter_success(self, mock_tk) -> None:
        result = open_native_folder_dialog()
        assert result == "/chosen"

    @patch("morphic.shared.file_browser._try_tkinter", return_value=None)
    @patch("morphic.shared.file_browser.platform.system", return_value="Linux")
    @patch(
        "morphic.shared.file_browser._try_zenity",
        return_value="/zenity_dir",
    )
    def test_linux_zenity_fallback(self, mock_z, mock_sys, mock_tk) -> None:
        result = open_native_folder_dialog()
        assert result == "/zenity_dir"

    @patch("morphic.shared.file_browser._try_tkinter", return_value=None)
    @patch("morphic.shared.file_browser.platform.system", return_value="Linux")
    @patch("morphic.shared.file_browser._try_zenity", return_value=None)
    @patch(
        "morphic.shared.file_browser._try_kdialog",
        return_value="/kde_dir",
    )
    def test_linux_kdialog_fallback(
        self, mock_k, mock_z, mock_sys, mock_tk,
    ) -> None:
        result = open_native_folder_dialog()
        assert result == "/kde_dir"

    @patch("morphic.shared.file_browser._try_tkinter", return_value=None)
    @patch(
        "morphic.shared.file_browser.platform.system",
        return_value="Darwin",
    )
    @patch(
        "morphic.shared.file_browser._try_osascript",
        return_value="/mac_dir",
    )
    def test_macos_fallback(self, mock_osa, mock_sys, mock_tk) -> None:
        result = open_native_folder_dialog()
        assert result == "/mac_dir"

    @patch("morphic.shared.file_browser._try_tkinter", return_value=None)
    @patch(
        "morphic.shared.file_browser.platform.system",
        return_value="Windows",
    )
    @patch(
        "morphic.shared.file_browser._try_powershell",
        return_value="C:\\dir",
    )
    def test_windows_fallback(self, mock_ps, mock_sys, mock_tk) -> None:
        result = open_native_folder_dialog()
        assert result == "C:\\dir"

    @patch("morphic.shared.file_browser._try_tkinter", return_value=None)
    @patch(
        "morphic.shared.file_browser.platform.system",
        return_value="Linux",
    )
    @patch("morphic.shared.file_browser._try_zenity", return_value=None)
    @patch("morphic.shared.file_browser._try_kdialog", return_value=None)
    def test_all_fail_returns_none(
        self, mock_k, mock_z, mock_sys, mock_tk,
    ) -> None:
        result = open_native_folder_dialog()
        assert result is None

    def test_default_initial_dir(self) -> None:
        with patch(
            "morphic.shared.file_browser._try_tkinter",
            return_value="/chosen",
        ) as mock_tk:
            open_native_folder_dialog()
            assert mock_tk.called
