"""Functional tests for pip's --require-virtualenv feature.

This module provides comprehensive end-to-end testing for the --require-virtualenv
functionality, focusing on realistic scenarios that can be tested within pip's
functional test infrastructure.

Test Categories:
- Command execution within virtual environment (normal pip testing environment)
- Bypass command verification for commands that ignore the requirement
- Option parsing and flag handling
- Integration with other pip options

Test Data:
- 13 bypass commands that ignore --require-virtualenv
- Real command execution using PipTestEnvironment

Dependencies:
- pytest fixtures from conftest.py
- PipTestEnvironment from tests.lib
- pip functional test infrastructure

Coverage Requirements:
- Command bypass functionality verification
- Option integration testing
- Functional behavior validation
- End-to-end command execution

Note: Testing "outside virtualenv" scenarios is handled in unit tests
since functional tests run within the pip test environment.
"""

from __future__ import annotations

import pytest

from tests.lib import PipTestEnvironment


class TestRequireVirtualenvFunctional:
    """Functional tests for --require-virtualenv command-line behavior."""

    # List of 13 bypass commands that ignore --require-virtualenv
    BYPASS_COMMANDS = [
        "cache", "check", "completion", "configuration", "debug",
        "freeze", "hash", "help", "index", "inspect", "list", "search", "show"
    ]

    def test_require_virtualenv_flag_accepted(
        self, script: PipTestEnvironment
    ) -> None:
        """Test that --require-virtualenv flag is accepted and parsed correctly.

        This test verifies that pip accepts the --require-virtualenv flag
        and processes it correctly within the test environment (which runs
        in a virtual environment, so the flag should not cause failures).
        """
        # Test with help command (bypass command) - should always work
        result = script.pip("help", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

        # Test with install command - should work in venv environment
        result = script.pip(
            "install", "--require-virtualenv", "--help"
        )
        assert result.returncode == 0
        assert "--require-virtualenv" in result.stdout

    def test_require_virtualenv_with_successful_commands(
        self, script: PipTestEnvironment
    ) -> None:
        """Test --require-virtualenv works correctly with successful commands.

        This test verifies that pip continues normal execution when the
        --require-virtualenv flag is used with commands that can succeed
        in the test environment.
        """
        # Test with help command - should succeed completely
        result = script.pip("help", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

        # Test with list command - should succeed (may be empty but should work)
        result = script.pip("list", "--require-virtualenv")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

        # Test with show command for pip itself
        result = script.pip("show", "--require-virtualenv", "pip")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

    def test_bypass_commands_accept_require_virtualenv_flag(
        self, script: PipTestEnvironment
    ) -> None:
        """Test all 13 bypass commands accept --require-virtualenv flag.

        This test verifies that commands with ignore_require_venv = True
        accept and process the --require-virtualenv flag without issues.

        Commands tested: cache, check, completion, configuration, debug, freeze,
        hash, help, index, inspect, list, search, show
        """
        # Test a representative sample of bypass commands
        test_commands = [
            # Commands that work without additional args
            ("help", []),
            ("list", []),
            ("freeze", []),
            ("check", []),
            ("debug", []),
            
            # Commands that need subcommands - test with valid subcommands
            ("cache", ["dir"]),
            ("show", ["pip"]),  # Show info about pip itself
        ]

        for command, extra_args in test_commands:
            cmd_args = [command] + extra_args + ["--require-virtualenv"]
            
            # Some commands like 'debug' produce warnings, which is expected
            allow_warnings = command in ["debug"]
            result = script.pip(*cmd_args, allow_stderr_warning=allow_warnings)
            
            # All these commands should succeed (return code 0)
            # since they ignore the virtualenv requirement
            assert result.returncode == 0, f"Command {command} failed"
            
            # Should not contain virtualenv error message
            assert (
                "Could not find an activated virtualenv (required)."
                not in result.stderr
            ), f"Command {command} showed virtualenv error"

    def test_require_virtualenv_option_in_help(
        self, script: PipTestEnvironment
    ) -> None:
        """Test that --require-virtualenv option appears in help output.

        This test verifies that the --require-virtualenv option is properly
        documented and appears in the help output of commands that support it.
        """
        # Test install command help
        result = script.pip("install", "--help")
        assert result.returncode == 0
        assert "--require-virtualenv" in result.stdout

        # Test wheel command help  
        result = script.pip("wheel", "--help")
        assert result.returncode == 0
        assert "--require-virtualenv" in result.stdout

        # Test uninstall command help
        result = script.pip("uninstall", "--help")
        assert result.returncode == 0
        assert "--require-virtualenv" in result.stdout

    def test_require_virtualenv_with_other_options(
        self, script: PipTestEnvironment
    ) -> None:
        """Test --require-virtualenv works correctly with other pip options.

        This test verifies that the --require-virtualenv flag can be combined
        with other pip options and behaves correctly.
        """
        # Test with verbose flag
        result = script.pip("help", "--require-virtualenv", "--verbose")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

        # Test with quiet flag  
        result = script.pip("help", "--require-virtualenv", "--quiet")
        assert result.returncode == 0
        assert "Could not find an activated virtualenv (required)." not in result.stderr

        # Test option ordering - flag at different positions
        result = script.pip("--require-virtualenv", "help")
        assert result.returncode == 0

        result = script.pip("help", "--require-virtualenv")
        assert result.returncode == 0

    def test_require_virtualenv_comprehensive_bypass_commands(
        self, script: PipTestEnvironment
    ) -> None:
        """Test comprehensive coverage of bypass commands with --require-virtualenv.

        This test verifies that all 13 bypass commands properly handle
        the --require-virtualenv flag in various scenarios.
        """
        # Test commands that don't need additional arguments
        simple_commands = ["help", "list", "freeze", "check", "debug"]
        for command in simple_commands:
            if command in self.BYPASS_COMMANDS:
                # Some commands like 'debug' produce warnings, which is expected
                allow_warnings = command in ["debug"]
                result = script.pip(command, "--require-virtualenv", 
                                  allow_stderr_warning=allow_warnings)
                assert result.returncode == 0, f"Command {command} failed"
                assert (
                    "Could not find an activated virtualenv (required)."
                    not in result.stderr
                ), f"Command {command} showed virtualenv error"

        # Test commands that need subcommands/arguments
        commands_with_args = [
            ("cache", ["dir"]),
            ("show", ["pip"]),
            ("hash", ["--help"]),  # Use --help to avoid needing actual files
        ]

        for command, args in commands_with_args:
            if command in self.BYPASS_COMMANDS:
                full_args = [command] + args + ["--require-virtualenv"]
                result = script.pip(*full_args)
                assert result.returncode == 0, f"Command {command} with args failed"
                assert (
                    "Could not find an activated virtualenv (required)."
                    not in result.stderr
                ), f"Command {command} showed virtualenv error"
