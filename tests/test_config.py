import os
from pathlib import Path
from unittest import mock

import pytest

from snow.config import get_db_path


def test_get_db_path_uses_xdg_data_home():
    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/xdg/path"}):
        with mock.patch.object(Path, "mkdir"):
            result = get_db_path()
            assert result == Path("/custom/xdg/path/snow/snow.db")


def test_get_db_path_uses_local_share_when_xdg_not_set():
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(Path, "exists", return_value=True):
            with mock.patch.object(Path, "mkdir"):
                result = get_db_path()
                expected = Path.home() / ".local" / "share" / "snow" / "snow.db"
                assert result == expected


def test_get_db_path_fallback_to_cwd_when_local_share_missing():
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.object(Path, "exists", return_value=False):
            with mock.patch.object(Path, "mkdir"):
                result = get_db_path()
                expected = Path.cwd() / "snow" / "snow.db"
                assert result == expected


def test_get_db_path_creates_directory():
    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/test_xdg"}):
        mock_path = mock.MagicMock(spec=Path)
        mock_path.__truediv__ = mock.MagicMock(return_value=mock_path)
        mock_path.mkdir = mock.MagicMock()

        with mock.patch("snow.config.Path") as MockPath:
            MockPath.return_value = mock_path
            MockPath.cwd.return_value = mock_path
            result = get_db_path()

            mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
