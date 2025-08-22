from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from optparse import Values
from pathlib import Path
from typing import Callable, NoReturn
from unittest.mock import Mock, patch

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import SUCCESS, VIRTUALENV_NOT_FOUND
from pip._internal.utils import temp_dir
from pip._internal.utils.logging import BrokenStdoutLoggingError
from pip._internal.utils.temp_dir import TempDirectory


@pytest.fixture
def fixed_time() -> Iterator[None]:
    # Patch time so logs contain a constant timestamp. time.time_ns is used by
    # logging starting with Python 3.13.
    year2019 = 1547704837.040001 + time.timezone
    with patch("time.time", lambda: year2019):
        with patch("time.time_ns", lambda: int(year2019 * 1e9)):
            yield


class FakeCommand(Command):
    _name = "fake"

    def __init__(
        self, run_func: Callable[[], int] | None = None, error: bool = False
    ) -> None:
        if error:

            def run_func() -> int:
                raise SystemExit(1)

        self.run_func = run_func
        super().__init__(self._name, self._name)

    def main(self, args: list[str]) -> int:
        args.append("--disable-pip-version-check")
        return super().main(args)

    def run(self, options: Values, args: list[str]) -> int:
        logging.getLogger("pip.tests").info("fake")
        # Return SUCCESS from run if run_func is not provided
        if self.run_func:
            return self.run_func()
        else:
            return SUCCESS


class FakeCommandWithUnicode(FakeCommand):
    _name = "fake_unicode"

    def run(self, options: Values, args: list[str]) -> int:
        logging.getLogger("pip.tests").info(b"bytes here \xe9")
        logging.getLogger("pip.tests").info(b"unicode here \xc3\xa9".decode("utf-8"))
        return SUCCESS


class TestCommand:
    def call_main(self, capsys: pytest.CaptureFixture[str], args: list[str]) -> str:
        """
        Call command.main(), and return the command's stderr.
        """

        def raise_broken_stdout() -> NoReturn:
            raise BrokenStdoutLoggingError()

        cmd = FakeCommand(run_func=raise_broken_stdout)
        status = cmd.main(args)
        assert status == 1
        stderr = capsys.readouterr().err

        return stderr

    def test_raise_broken_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """
        Test raising BrokenStdoutLoggingError.
        """
        stderr = self.call_main(capsys, [])

        assert stderr.rstrip() == "ERROR: Pipe to stdout was broken"

    def test_raise_broken_stdout__debug_logging(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """
        Test raising BrokenStdoutLoggingError with debug logging enabled.
        """
        stderr = self.call_main(capsys, ["-vv"])

        assert "ERROR: Pipe to stdout was broken" in stderr
        assert "Traceback (most recent call last):" in stderr


@patch("pip._internal.cli.index_command.Command.handle_pip_version_check")
def test_handle_pip_version_check_called(mock_handle_version_check: Mock) -> None:
    """
    Check that Command.handle_pip_version_check() is called.
    """
    cmd = FakeCommand()
    cmd.main([])
    mock_handle_version_check.assert_called_once()


def test_debug_enables_verbose_logs() -> None:
    cmd = FakeCommand()
    cmd.main(["fake", "--debug"])
    assert cmd.verbosity >= 2


def test_log_command_success(fixed_time: None, tmpdir: Path) -> None:
    """Test the --log option logs when command succeeds."""
    cmd = FakeCommand()
    log_path = os.path.join(tmpdir, "log")
    cmd.main(["fake", "--log", log_path])
    with open(log_path) as f:
        assert f.read().rstrip() == "2019-01-17T06:00:37,040 fake"


def test_log_command_error(fixed_time: None, tmpdir: Path) -> None:
    """Test the --log option logs when command fails."""
    cmd = FakeCommand(error=True)
    log_path = os.path.join(tmpdir, "log")
    cmd.main(["fake", "--log", log_path])
    with open(log_path) as f:
        assert f.read().startswith("2019-01-17T06:00:37,040 fake")


def test_log_file_command_error(fixed_time: None, tmpdir: Path) -> None:
    """Test the --log-file option logs (when there's an error)."""
    cmd = FakeCommand(error=True)
    log_file_path = os.path.join(tmpdir, "log_file")
    cmd.main(["fake", "--log-file", log_file_path])
    with open(log_file_path) as f:
        assert f.read().startswith("2019-01-17T06:00:37,040 fake")


def test_log_unicode_messages(fixed_time: None, tmpdir: Path) -> None:
    """Tests that logging bytestrings and unicode objects
    don't break logging.
    """
    cmd = FakeCommandWithUnicode()
    log_path = os.path.join(tmpdir, "log")
    cmd.main(["fake_unicode", "--log", log_path])


@pytest.mark.no_auto_tempdir_manager
def test_base_command_provides_tempdir_helpers() -> None:
    assert temp_dir._tempdir_manager is None
    assert temp_dir._tempdir_registry is None

    def assert_helpers_set(options: Values, args: list[str]) -> int:
        assert temp_dir._tempdir_manager is not None
        assert temp_dir._tempdir_registry is not None
        return SUCCESS

    c = Command("fake", "fake")
    # https://github.com/python/mypy/issues/2427
    c.run = Mock(side_effect=assert_helpers_set)  # type: ignore[method-assign]
    assert c.main(["fake"]) == SUCCESS
    c.run.assert_called_once()


not_deleted = "not_deleted"


@pytest.mark.parametrize("kind,exists", [(not_deleted, True), ("deleted", False)])
@pytest.mark.no_auto_tempdir_manager
def test_base_command_global_tempdir_cleanup(kind: str, exists: bool) -> None:
    assert temp_dir._tempdir_manager is None
    assert temp_dir._tempdir_registry is None

    class Holder:
        value: str

    def create_temp_dirs(options: Values, args: list[str]) -> int:
        assert c.tempdir_registry is not None
        c.tempdir_registry.set_delete(not_deleted, False)
        Holder.value = TempDirectory(kind=kind, globally_managed=True).path
        return SUCCESS

    c = Command("fake", "fake")
    # https://github.com/python/mypy/issues/2427
    c.run = Mock(side_effect=create_temp_dirs)  # type: ignore[method-assign]
    assert c.main(["fake"]) == SUCCESS
    c.run.assert_called_once()
    assert os.path.exists(Holder.value) == exists


@pytest.mark.parametrize("kind,exists", [(not_deleted, True), ("deleted", False)])
@pytest.mark.no_auto_tempdir_manager
def test_base_command_local_tempdir_cleanup(kind: str, exists: bool) -> None:
    assert temp_dir._tempdir_manager is None
    assert temp_dir._tempdir_registry is None

    def create_temp_dirs(options: Values, args: list[str]) -> int:
        assert c.tempdir_registry is not None
        c.tempdir_registry.set_delete(not_deleted, False)

        with TempDirectory(kind=kind) as d:
            path = d.path
            assert os.path.exists(path)
        assert os.path.exists(path) == exists
        return SUCCESS

    c = Command("fake", "fake")
    # https://github.com/python/mypy/issues/2427
    c.run = Mock(side_effect=create_temp_dirs)  # type: ignore[method-assign]
    assert c.main(["fake"]) == SUCCESS
    c.run.assert_called_once()


class FakeCommandIgnoreVenv(FakeCommand):
    """Test command that ignores require_venv flag."""
    _name = "fake_ignore_venv"
    ignore_require_venv = True


class FakeCommandRespectVenv(FakeCommand):
    """Test command that respects require_venv flag."""
    _name = "fake_respect_venv"
    ignore_require_venv = False


class TestRequireVirtualenv:
    """Test --require-virtualenv enforcement logic."""
    
    def test_require_venv_in_virtualenv_command_executes(self) -> None:
        """Test that command executes successfully when in virtualenv with require_venv=True."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=True):
            cmd = FakeCommandRespectVenv()
            # Simulate --require-virtualenv flag
            status = cmd.main(["--require-virtualenv"])
            assert status == SUCCESS

    def test_require_venv_not_in_virtualenv_command_exits(self) -> None:
        """Test that command exits with VIRTUALENV_NOT_FOUND when not in virtualenv with require_venv=True."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandRespectVenv()
            with pytest.raises(SystemExit) as exc_info:
                cmd.main(["--require-virtualenv"])
            
            # Verify exit code is VIRTUALENV_NOT_FOUND (3)
            assert exc_info.value.code == VIRTUALENV_NOT_FOUND

    def test_no_require_venv_not_in_virtualenv_command_executes(self) -> None:
        """Test that command executes successfully when not in virtualenv and require_venv=False."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandRespectVenv()
            # Don't pass --require-virtualenv flag
            status = cmd.main([])
            assert status == SUCCESS

    def test_no_require_venv_in_virtualenv_command_executes(self) -> None:
        """Test that command executes successfully when in virtualenv and require_venv=False."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=True):
            cmd = FakeCommandRespectVenv()
            # Don't pass --require-virtualenv flag
            status = cmd.main([])
            assert status == SUCCESS

    def test_ignore_require_venv_true_not_in_virtualenv_command_executes(self) -> None:
        """Test that command executes when ignore_require_venv=True even with require_venv=True and not in virtualenv."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandIgnoreVenv()
            # Pass --require-virtualenv flag but command ignores it
            status = cmd.main(["--require-virtualenv"])
            assert status == SUCCESS

    def test_ignore_require_venv_true_in_virtualenv_command_executes(self) -> None:
        """Test that command executes when ignore_require_venv=True with require_venv=True and in virtualenv."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=True):
            cmd = FakeCommandIgnoreVenv()
            # Pass --require-virtualenv flag
            status = cmd.main(["--require-virtualenv"])
            assert status == SUCCESS

    def test_ignore_require_venv_false_not_in_virtualenv_with_require_venv_exits(self) -> None:
        """Test that command exits when ignore_require_venv=False, require_venv=True, and not in virtualenv."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandRespectVenv()
            with pytest.raises(SystemExit) as exc_info:
                cmd.main(["--require-virtualenv"])
            
            # Verify exit code is VIRTUALENV_NOT_FOUND (3)
            assert exc_info.value.code == VIRTUALENV_NOT_FOUND

    def test_ignore_require_venv_false_in_virtualenv_command_executes(self) -> None:
        """Test that command executes when ignore_require_venv=False, require_venv=True, and in virtualenv."""
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=True):
            cmd = FakeCommandRespectVenv()
            status = cmd.main(["--require-virtualenv"])
            assert status == SUCCESS

    def test_truth_matrix_comprehensive_coverage(self) -> None:
        """Test all 8 combinations of truth matrix for comprehensive coverage."""
        
        # Truth matrix test cases: (has_venv, require_venv, ignore_require_venv, expected_behavior)
        test_cases = [
            # has_venv=True cases - all should execute successfully
            (True, True, True, "executes"),    # In venv, require venv, ignore flag -> executes
            (True, True, False, "executes"),   # In venv, require venv, respect flag -> executes  
            (True, False, True, "executes"),   # In venv, no require venv, ignore flag -> executes
            (True, False, False, "executes"),  # In venv, no require venv, respect flag -> executes
            
            # has_venv=False cases - only one should exit with error
            (False, True, True, "executes"),   # No venv, require venv, ignore flag -> executes (bypassed)
            (False, True, False, "exits"),     # No venv, require venv, respect flag -> exits with error
            (False, False, True, "executes"),  # No venv, no require venv, ignore flag -> executes
            (False, False, False, "executes"), # No venv, no require venv, respect flag -> executes
        ]
        
        for has_venv, require_venv, ignore_require_venv, expected_behavior in test_cases:
            
            # Set up command with appropriate ignore_require_venv setting
            if ignore_require_venv:
                cmd = FakeCommandIgnoreVenv()
            else:
                cmd = FakeCommandRespectVenv()
            
            # Mock virtualenv state
            with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=has_venv):
                # Build command arguments
                args = ["--require-virtualenv"] if require_venv else []
                
                if expected_behavior == "executes":
                    # Command should execute successfully
                    status = cmd.main(args)
                    assert status == SUCCESS, f"Failed case: has_venv={has_venv}, require_venv={require_venv}, ignore_require_venv={ignore_require_venv}"
                    
                elif expected_behavior == "exits":
                    # Command should exit with VIRTUALENV_NOT_FOUND
                    with pytest.raises(SystemExit) as exc_info:
                        cmd.main(args)
                    
                    assert exc_info.value.code == VIRTUALENV_NOT_FOUND, f"Wrong exit code for case: has_venv={has_venv}, require_venv={require_venv}, ignore_require_venv={ignore_require_venv}"

    def test_virtualenv_detection_integration(self) -> None:
        """Test that the virtualenv detection properly integrates with the require_venv logic."""
        
        # Test with mocked virtualenv detection returning False
        with patch("pip._internal.cli.base_command.running_under_virtualenv") as mock_venv:
            mock_venv.return_value = False
            
            cmd = FakeCommandRespectVenv()
            with pytest.raises(SystemExit) as exc_info:
                cmd.main(["--require-virtualenv"])
            
            # Verify running_under_virtualenv was called
            mock_venv.assert_called_once()
            assert exc_info.value.code == VIRTUALENV_NOT_FOUND
            
        # Test with mocked virtualenv detection returning True
        with patch("pip._internal.cli.base_command.running_under_virtualenv") as mock_venv:
            mock_venv.return_value = True
            
            cmd = FakeCommandRespectVenv()
            status = cmd.main(["--require-virtualenv"])
            
            # Verify running_under_virtualenv was called and command succeeded
            mock_venv.assert_called_once()
            assert status == SUCCESS

    def test_require_venv_conditional_logic_coverage(self) -> None:
        """Test the specific conditional logic from base_command.py lines 219-223."""
        
        # Test the exact conditional: if options.require_venv and not self.ignore_require_venv:
        
        # Case 1: options.require_venv=True, self.ignore_require_venv=False -> condition is True
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandRespectVenv()  # ignore_require_venv = False
            with pytest.raises(SystemExit) as exc_info:
                cmd.main(["--require-virtualenv"])  # require_venv = True
            
            assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        
        # Case 2: options.require_venv=True, self.ignore_require_venv=True -> condition is False
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandIgnoreVenv()  # ignore_require_venv = True
            status = cmd.main(["--require-virtualenv"])  # require_venv = True
            assert status == SUCCESS
        
        # Case 3: options.require_venv=False, self.ignore_require_venv=False -> condition is False
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandRespectVenv()  # ignore_require_venv = False
            status = cmd.main([])  # require_venv = False (no --require-virtualenv flag)
            assert status == SUCCESS
        
        # Case 4: options.require_venv=False, self.ignore_require_venv=True -> condition is False
        with patch("pip._internal.cli.base_command.running_under_virtualenv", return_value=False):
            cmd = FakeCommandIgnoreVenv()  # ignore_require_venv = True
            status = cmd.main([])  # require_venv = False (no --require-virtualenv flag)
            assert status == SUCCESS
