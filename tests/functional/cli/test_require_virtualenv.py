"""Functional tests for pip's --require-virtualenv feature.

This module provides comprehensive end-to-end testing for the --require-virtualenv
functionality, verifying command execution behavior including subprocess tests for
failure outside virtualenv, success in virtualenv, bypass command functionality,
and error message format validation.

Test Categories:
- Subprocess execution tests with different virtual environment states
- Bypass command verification for commands that ignore the requirement
- Error message and exit code validation
- Command-line behavior testing

Test Data:
- Mock virtual environment state using monkeypatch
- 13 bypass commands that ignore --require-virtualenv

Dependencies:
- pytest fixtures from conftest.py
- PipTestEnvironment from tests.lib
- Mock virtual environment detection

Coverage Requirements:
- Exit code 3 (VIRTUALENV_NOT_FOUND) verification
- Error message content validation
- Command bypass functionality
- Virtual environment state mocking
"""

from __future__ import annotations

import pytest

from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND

from tests.lib import PipTestEnvironment


class TestRequireVirtualenvFunctional:
    """Functional tests for --require-virtualenv command-line behavior."""
    
    # List of 13 bypass commands that ignore --require-virtualenv
    BYPASS_COMMANDS = [
        "cache", "check", "completion", "configuration", "debug", 
        "freeze", "hash", "help", "index", "inspect", "list", "search", "show"
    ]

    @pytest.fixture
    def mock_not_in_virtualenv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fixture to simulate not being in a virtual environment."""
        monkeypatch.setattr(
            "pip._internal.utils.virtualenv.running_under_virtualenv",
            lambda: False
        )

    @pytest.fixture  
    def mock_in_virtualenv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fixture to simulate being in a virtual environment."""
        monkeypatch.setattr(
            "pip._internal.utils.virtualenv.running_under_virtualenv", 
            lambda: True
        )

    def test_pip_fails_outside_venv_with_require_virtualenv(
        self, script: PipTestEnvironment, mock_not_in_virtualenv: None
    ) -> None:
        """Test pip fails with exit code 3 when --require-virtualenv is set and not in a virtual environment.
        
        This test verifies that pip properly detects when it's running outside a virtual
        environment and exits with the correct error code (VIRTUALENV_NOT_FOUND = 3) when
        the --require-virtualenv flag is specified.
        """
        # Test with install command (non-bypass command)
        result = script.pip(
            "install", "--require-virtualenv", "simple", 
            expect_error=True
        )
        
        # Verify exit code is VIRTUALENV_NOT_FOUND (3)
        assert result.returncode == VIRTUALENV_NOT_FOUND
        
        # Verify critical error message is present
        assert "Could not find an activated virtualenv (required)." in result.stderr
        
        # Test with another non-bypass command to ensure consistency
        result = script.pip(
            "wheel", "--require-virtualenv", "simple",
            expect_error=True
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_pip_succeeds_in_venv_with_require_virtualenv(
        self, script: PipTestEnvironment, mock_in_virtualenv: None
    ) -> None:
        """Test pip succeeds when --require-virtualenv is set and running in a virtual environment.
        
        This test verifies that pip continues normal execution when it detects
        it's running inside a virtual environment, even with --require-virtualenv specified.
        """
        # Test install command continues to argument parsing (will fail due to missing package)
        # but should NOT fail due to virtualenv requirement
        result = script.pip(
            "install", "--require-virtualenv", "nonexistent-package-12345",
            expect_error=True
        )
        
        # Should NOT exit with VIRTUALENV_NOT_FOUND - should fail later in the process
        assert result.returncode != VIRTUALENV_NOT_FOUND
        
        # Should not contain the virtualenv error message
        assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        # Test with help command which should succeed completely
        result = script.pip("help", "--require-virtualenv")
        
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

    def test_bypass_commands_work_outside_venv(
        self, script: PipTestEnvironment, mock_not_in_virtualenv: None
    ) -> None:
        """Test all 13 bypass commands ignore the requirement even when flag is set.
        
        This test verifies that commands with ignore_require_venv = True continue
        to function outside virtual environments even when --require-virtualenv is specified.
        
        Commands tested: cache, check, completion, configuration, debug, freeze, 
        hash, help, index, inspect, list, search, show
        """
        for command in self.BYPASS_COMMANDS:
            # Test each bypass command - they should NOT exit with VIRTUALENV_NOT_FOUND
            # even when outside a venv with --require-virtualenv specified
            if command == "help":
                # Help command should succeed completely
                result = script.pip(command, "--require-virtualenv")
                assert result.returncode == 0
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                
            elif command == "cache":
                # Cache needs a subcommand - test with dir
                result = script.pip(command, "dir", "--require-virtualenv")
                # Should not fail due to virtualenv requirement
                assert result.returncode != VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                
            elif command in ["completion", "configuration"]:
                # These commands need subcommands but should not fail due to virtualenv
                result = script.pip(command, "--require-virtualenv", expect_error=True)
                # Should fail due to missing subcommand, NOT due to virtualenv requirement
                assert result.returncode != VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                
            elif command == "index":
                # Index command needs subcommand - test with versions
                result = script.pip(command, "versions", "simple", "--require-virtualenv")
                # Should not fail due to virtualenv requirement
                assert result.returncode != VIRTUALENV_NOT_FOUND  
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                
            else:
                # For other bypass commands, test basic execution
                result = script.pip(command, "--require-virtualenv", expect_error=True)
                
                # Should NOT exit due to virtualenv requirement
                assert result.returncode != VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." not in result.stderr

    def test_error_message_format(
        self, script: PipTestEnvironment, mock_not_in_virtualenv: None
    ) -> None:
        """Test user-facing error output format and content.
        
        This test verifies the exact format and content of the error message
        displayed when pip fails due to --require-virtualenv outside a virtual environment.
        """
        result = script.pip(
            "install", "--require-virtualenv", "simple",
            expect_error=True
        )
        
        # Verify exit code
        assert result.returncode == VIRTUALENV_NOT_FOUND
        
        # Verify exact error message format
        expected_message = "Could not find an activated virtualenv (required)."
        assert expected_message in result.stderr
        
        # Verify it's logged as a critical error (should appear in stderr)
        assert "ERROR" in result.stderr or "CRITICAL" in result.stderr
        
        # Test with different command to ensure message consistency
        result = script.pip(
            "uninstall", "--require-virtualenv", "simple",
            expect_error=True
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert expected_message in result.stderr

    def test_require_virtualenv_with_other_options(
        self, script: PipTestEnvironment, mock_not_in_virtualenv: None
    ) -> None:
        """Test --require-virtualenv works correctly with other pip options.
        
        This test verifies that the virtualenv requirement check occurs early
        in the process and works correctly when combined with other options.
        """
        # Test with verbose flag
        result = script.pip(
            "install", "--require-virtualenv", "--verbose", "simple",
            expect_error=True
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr
        
        # Test with quiet flag
        result = script.pip(
            "install", "--require-virtualenv", "--quiet", "simple",
            expect_error=True
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        # Even with --quiet, critical errors should still appear
        assert "Could not find an activated virtualenv (required)." in result.stderr
        
        # Test with help to ensure bypass still works with other options
        result = script.pip("help", "--require-virtualenv", "--verbose")
        
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

    def test_mixed_virtualenv_scenarios(
        self, script: PipTestEnvironment, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test various combinations of virtualenv states and command types.
        
        This test provides comprehensive coverage of different scenarios combining
        virtual environment states with bypass/non-bypass commands.
        """
        # Scenario 1: Non-bypass command outside venv with --require-virtualenv (should fail)
        monkeypatch.setattr(
            "pip._internal.utils.virtualenv.running_under_virtualenv",
            lambda: False
        )
        
        result = script.pip(
            "install", "--require-virtualenv", "simple",
            expect_error=True
        )
        assert result.returncode == VIRTUALENV_NOT_FOUND
        
        # Scenario 2: Bypass command outside venv with --require-virtualenv (should succeed/continue)
        result = script.pip("help", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        # Scenario 3: Non-bypass command inside venv with --require-virtualenv (should continue)
        monkeypatch.setattr(
            "pip._internal.utils.virtualenv.running_under_virtualenv",
            lambda: True
        )
        
        result = script.pip("help", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        # Scenario 4: Bypass command inside venv with --require-virtualenv (should continue)
        result = script.pip("list", "--require-virtualenv")
        # Should not fail due to virtualenv requirement
        assert result.returncode != VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." not in result.stderr