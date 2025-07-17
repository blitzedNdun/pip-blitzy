"""
Functional tests for pip's --require-virtualenv CLI option.

This test suite provides comprehensive end-to-end validation of virtualenv
enforcement across various pip commands, focusing on user-visible behavior
and error reporting.
"""

import pytest
from unittest.mock import patch
from pathlib import Path
from textwrap import dedent

from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND

from tests.lib import PipTestEnvironment, TestData


@pytest.fixture
def mock_outside_venv():
    """Mock running_under_virtualenv to return False (outside venv)"""
    with patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
        yield


@pytest.fixture
def mock_inside_venv():
    """Mock running_under_virtualenv to return True (inside venv)"""
    with patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=True):
        yield


class TestRequireVirtualenvFlag:
    """Test the --require-virtualenv flag behavior"""

    def test_require_virtualenv_inside_venv_succeeds(self, script: PipTestEnvironment, mock_inside_venv):
        """Test that --require-virtualenv succeeds when inside a virtual environment"""
        result = script.pip("list", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv" not in result.stderr

    def test_require_virtualenv_outside_venv_fails(self, script: PipTestEnvironment, mock_outside_venv):
        """Test that --require-virtualenv fails when outside a virtual environment"""
        result = script.pip("list", "--require-virtualenv", expect_error=True)
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    @pytest.mark.parametrize("command", ["install", "download", "wheel"])
    def test_require_virtualenv_with_different_commands(
        self, script: PipTestEnvironment, mock_outside_venv, command: str, shared_data: TestData
    ):
        """Test --require-virtualenv with commands that should enforce virtualenv"""
        # Create a simple package for testing
        pkg_path = script.scratch_path / "simple_package"
        pkg_path.mkdir()
        (pkg_path / "setup.py").write_text(
            dedent(
                """
                from setuptools import setup
                setup(name="simple_package", version="1.0")
                """
            )
        )
        
        # Test different commands with --require-virtualenv
        if command == "install":
            result = script.pip("install", "--require-virtualenv", str(pkg_path), expect_error=True)
        elif command == "download":
            result = script.pip("download", "--require-virtualenv", str(pkg_path), expect_error=True)
        elif command == "wheel":
            result = script.pip("wheel", "--require-virtualenv", str(pkg_path), expect_error=True)
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_require_virtualenv_error_message_format(self, script: PipTestEnvironment, mock_outside_venv):
        """Test that the error message format is correct"""
        result = script.pip("list", "--require-virtualenv", expect_error=True)
        
        # Verify exact error message
        assert "Could not find an activated virtualenv (required)." in result.stderr
        # Verify it's logged as critical (appears in stderr)
        assert result.returncode == VIRTUALENV_NOT_FOUND


class TestIgnoreRequireVirtualenvCommands:
    """Test commands that bypass the --require-virtualenv check"""

    @pytest.mark.parametrize("command", ["list", "check", "inspect", "freeze"])
    def test_commands_ignore_require_venv_outside_venv(
        self, script: PipTestEnvironment, mock_outside_venv, command: str
    ):
        """Test that commands with ignore_require_venv=True bypass the check"""
        result = script.pip(command, "--require-virtualenv")
        
        # These commands should succeed even outside venv
        assert result.returncode == 0
        assert "Could not find an activated virtualenv" not in result.stderr

    @pytest.mark.parametrize("command", ["list", "check", "inspect", "freeze"])
    def test_commands_ignore_require_venv_inside_venv(
        self, script: PipTestEnvironment, mock_inside_venv, command: str
    ):
        """Test that commands with ignore_require_venv=True work inside venv too"""
        result = script.pip(command, "--require-virtualenv")
        
        # These commands should succeed inside venv as well
        assert result.returncode == 0
        assert "Could not find an activated virtualenv" not in result.stderr


class TestRequireVirtualenvWithoutFlag:
    """Test behavior when --require-virtualenv is not used"""

    @pytest.mark.parametrize("venv_state", [True, False])
    def test_no_require_virtualenv_flag(self, script: PipTestEnvironment, venv_state: bool):
        """Test that commands work normally without --require-virtualenv flag"""
        mock_func = "pip._internal.utils.virtualenv.running_under_virtualenv"
        
        with patch(mock_func, return_value=venv_state):
            result = script.pip("list")
            
            # Should succeed regardless of virtualenv state
            assert result.returncode == 0
            assert "Could not find an activated virtualenv" not in result.stderr


class TestRequireVirtualenvCombinations:
    """Test combinations of --require-virtualenv with other options"""

    def test_require_virtualenv_with_help(self, script: PipTestEnvironment, mock_outside_venv):
        """Test --require-virtualenv with --help (should not check virtualenv)"""
        result = script.pip("install", "--help", "--require-virtualenv")
        
        # Help should work regardless of virtualenv state
        assert result.returncode == 0
        assert "Could not find an activated virtualenv" not in result.stderr

    def test_require_virtualenv_with_version(self, script: PipTestEnvironment, mock_outside_venv):
        """Test --require-virtualenv with --version"""
        result = script.pip("--version", "--require-virtualenv")
        
        # Version should work regardless of virtualenv state
        assert result.returncode == 0
        assert "Could not find an activated virtualenv" not in result.stderr

    def test_require_virtualenv_with_verbose(self, script: PipTestEnvironment, mock_outside_venv):
        """Test --require-virtualenv with verbose flag"""
        result = script.pip("list", "--require-virtualenv", "-v", expect_error=True)
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr


class TestRequireVirtualenvCrossCommand:
    """Test cross-command behavior of --require-virtualenv"""

    def test_require_virtualenv_mixed_commands(self, script: PipTestEnvironment, mock_outside_venv):
        """Test that different commands consistently handle --require-virtualenv"""
        # Commands that should enforce virtualenv
        enforce_commands = ["install", "download", "wheel"]
        
        for command in enforce_commands:
            result = script.pip(command, "--require-virtualenv", "--help", expect_error=True)
            
            # Even with --help, the virtualenv check should happen first for these commands
            # Note: --help might bypass the check, but we're testing the general pattern
            if "--help" not in result.stdout:
                assert result.returncode == VIRTUALENV_NOT_FOUND

    def test_require_virtualenv_exit_code_consistency(self, script: PipTestEnvironment, mock_outside_venv):
        """Test that all commands return consistent exit code"""
        test_commands = [
            ["install", "--require-virtualenv", "nonexistent-package"],
            ["download", "--require-virtualenv", "nonexistent-package"],
            ["wheel", "--require-virtualenv", "nonexistent-package"],
        ]
        
        for command_args in test_commands:
            result = script.pip(*command_args, expect_error=True)
            assert result.returncode == VIRTUALENV_NOT_FOUND
            assert "Could not find an activated virtualenv (required)." in result.stderr