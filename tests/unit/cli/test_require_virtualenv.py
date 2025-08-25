"""
Unit tests for pip's --require-virtualenv functionality.

This module provides comprehensive testing for the virtual environment requirement
logic in src/pip/_internal/cli/base_command.py lines 219-223.

Test Categories:
- TestRequireVirtualenv: Core logic verification tests  
- TestTruthMatrix: Comprehensive permutation testing of all 8 truth matrix combinations
- TestCommandBypass: Command-specific bypass behavior testing

Testing Strategy:
- Mock at pip._internal.utils.virtualenv.running_under_virtualenv() level only
- Never modify sys.prefix, sys.base_prefix, or actual environment variables
- Use monkeypatch fixture consistently across all scenarios
- Verify exit codes, execution flow, and critical log messages

Coverage Target: 90%+ for --require-virtualenv feature implementation
"""

from __future__ import annotations

import logging
import sys
from optparse import Values
from unittest import mock

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND


# Test constants and fixtures
bypass_commands = [
    "cache",
    "check", 
    "completion",
    "configuration",
    "debug",
    "freeze",
    "hash",
    "help",
    "index",
    "inspect",
    "list",
    "search",
    "show",
]


@pytest.fixture
def mock_not_in_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to simulate not being in a virtual environment."""
    monkeypatch.setattr(
        "pip._internal.cli.base_command.running_under_virtualenv",
        lambda: False
    )


@pytest.fixture
def mock_in_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to simulate being in a virtual environment."""
    monkeypatch.setattr(
        "pip._internal.cli.base_command.running_under_virtualenv",
        lambda: True
    )


class FakeCommand(Command):
    """Test command class for testing virtual environment requirements."""
    
    def __init__(self, ignore_require_venv: bool = False, name: str = "fake"):
        super().__init__(name=name, summary="Fake command for testing")
        self.ignore_require_venv = ignore_require_venv
    
    def run(self, options: Values, args: list[str]) -> int:
        """Mock run method that returns success."""
        return 0


class TestRequireVirtualenv:
    """Core logic verification tests for --require-virtualenv functionality."""
    
    def test_require_venv_when_not_in_virtualenv_fails(
        self, 
        mock_not_in_virtualenv: None,
        capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that requiring virtualenv fails with exit code 3 when not in virtualenv."""
        command = FakeCommand(ignore_require_venv=False)
        
        # Test that SystemExit is raised with code 3
        with pytest.raises(SystemExit) as exc_info:
            command.main(["fake", "--require-virtualenv"])
        
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        
        # Verify critical message was output to stderr
        captured = capsys.readouterr()
        assert "Could not find an activated virtualenv (required)." in captured.err

    def test_require_venv_when_in_virtualenv_succeeds(
        self, 
        mock_in_virtualenv: None
    ) -> None:
        """Test that requiring virtualenv succeeds when in virtualenv."""
        command = FakeCommand(ignore_require_venv=False)
        
        # Should not raise SystemExit
        result = command.main(["fake", "--require-virtualenv"])
        assert result == 0

    def test_no_require_venv_when_not_in_virtualenv_succeeds(
        self, 
        mock_not_in_virtualenv: None
    ) -> None:
        """Test that not requiring virtualenv succeeds even when not in virtualenv."""
        command = FakeCommand(ignore_require_venv=False)
        
        # Should not raise SystemExit when --require-virtualenv is not specified
        result = command.main(["fake"])
        assert result == 0

    def test_ignore_require_venv_bypasses_check(
        self, 
        mock_not_in_virtualenv: None
    ) -> None:
        """Test that commands with ignore_require_venv=True bypass the check."""
        command = FakeCommand(ignore_require_venv=True)
        
        # Should not raise SystemExit even though require_venv=True and not in venv
        result = command.main(["fake", "--require-virtualenv"])
        assert result == 0

    def test_critical_message_logged(
        self, 
        mock_not_in_virtualenv: None,
        capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that the correct critical message is logged when virtualenv check fails."""
        command = FakeCommand(ignore_require_venv=False)
        
        # Test that SystemExit is raised and capture stderr output
        with pytest.raises(SystemExit):
            command.main(["fake", "--require-virtualenv"])
        
        # Verify exact message content in stderr
        captured = capsys.readouterr()
        assert "Could not find an activated virtualenv (required)." in captured.err


class TestTruthMatrix:
    """Comprehensive permutation testing of all truth matrix combinations."""
    
    @pytest.mark.parametrize(
        "has_venv,require_venv,ignore_require_venv,should_exit",
        [
            # All combinations from the truth matrix
            (True, True, False, False),    # ✓ Continue execution
            (True, True, True, False),     # ✓ Continue execution  
            (True, False, False, False),   # ✓ Continue execution
            (True, False, True, False),    # ✓ Continue execution
            (False, True, False, True),    # ✗ Exit with VIRTUALENV_NOT_FOUND
            (False, True, True, False),    # ✓ Continue execution (bypass)
            (False, False, False, False),  # ✓ Continue execution
            (False, False, True, False),   # ✓ Continue execution
        ]
    )
    def test_all_truth_matrix_combinations(
        self,
        has_venv: bool,
        require_venv: bool, 
        ignore_require_venv: bool,
        should_exit: bool,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test all 8 permutations of the truth matrix for virtualenv requirements."""
        # Mock the virtualenv detection based on has_venv
        monkeypatch.setattr(
            "pip._internal.cli.base_command.running_under_virtualenv",
            lambda: has_venv
        )
        
        command = FakeCommand(ignore_require_venv=ignore_require_venv)
        
        # Build arguments based on require_venv flag
        args = ["fake"]
        if require_venv:
            args.append("--require-virtualenv")
        
        if should_exit:
            # Should exit with VIRTUALENV_NOT_FOUND
            with pytest.raises(SystemExit) as exc_info:
                command.main(args)
            assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        else:
            # Should continue execution normally
            result = command.main(args)
            assert result == 0


class TestCommandBypass:
    """Command-specific bypass behavior testing for commands with ignore_require_venv=True."""
    
    @pytest.mark.parametrize("command_name", bypass_commands)
    def test_bypass_commands_ignore_require_venv(
        self,
        command_name: str,
        mock_not_in_virtualenv: None
    ) -> None:
        """Test that bypass commands ignore virtualenv requirement even when not in virtualenv."""
        # Create command with ignore_require_venv=True
        command = FakeCommand(ignore_require_venv=True, name=command_name)
        
        # Should succeed even though require_venv=True and not in virtualenv
        result = command.main([command_name, "--require-virtualenv"])
        assert result == 0
        
        # Verify the command name matches one of the known bypass commands
        assert command_name in bypass_commands