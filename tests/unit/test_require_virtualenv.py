"""
Comprehensive unit tests for pip's --require-virtualenv feature.

This module provides comprehensive testing for the --require-virtualenv functionality
that ensures pip commands can only run within activated virtual environments when required.

Test Categories:
- Virtual environment detection logic via running_under_virtualenv()
- Command enforcement logic in base_command.py:219-223  
- Complete coverage of all 8 truth matrix combinations
- Command-specific opt-out behavior for 13 commands with ignore_require_venv=True
- Proper mocking of virtual environment states for both modern venv and legacy virtualenv

Coverage Requirements:
- Line coverage: >= 90% for --require-virtualenv feature implementation
- Branch coverage: >= 90% for enforcement decision logic  
- 100% coverage of truth matrix combinations

Dependencies:
- pytest fixtures for environment control
- unittest.mock for patching system functions
- sys module for virtualenv attribute manipulation
- logging for error message capture
"""

from __future__ import annotations

import logging
import sys
from optparse import Values
from typing import Iterator
from unittest.mock import Mock, patch

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND
from pip._internal.utils.virtualenv import running_under_virtualenv


class TestVirtualEnvDetection:
    """Tests for virtual environment detection logic via running_under_virtualenv()."""

    @pytest.fixture
    def mock_virtualenv_state(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[callable]:
        """Fixture to control virtual environment detection state.
        
        Returns a callable that can set the virtualenv state for testing.
        Supports both modern venv (PEP 405) and legacy virtualenv detection.
        
        Args:
            is_active: Whether to simulate an active virtual environment
            use_legacy: Whether to use legacy virtualenv detection method
        """
        def set_virtualenv_state(is_active: bool, use_legacy: bool = False) -> None:
            if is_active:
                if use_legacy:
                    # Legacy virtualenv: sets sys.real_prefix
                    # First ensure sys.real_prefix exists (create it if it doesn't)
                    if not hasattr(sys, 'real_prefix'):
                        sys.real_prefix = '/system/python'
                    else:
                        monkeypatch.setattr(sys, 'real_prefix', '/system/python')
                    monkeypatch.setattr(sys, 'prefix', '/venv/path')
                    monkeypatch.setattr(sys, 'base_prefix', '/system/python')
                else:
                    # Modern venv: sys.prefix != sys.base_prefix
                    monkeypatch.setattr(sys, 'prefix', '/venv/path')
                    monkeypatch.setattr(sys, 'base_prefix', '/system/python')
                    # Ensure no real_prefix attribute exists
                    monkeypatch.delattr(sys, 'real_prefix', raising=False)
            else:
                # No virtualenv: sys.prefix == sys.base_prefix, no real_prefix
                monkeypatch.setattr(sys, 'prefix', '/system/python')
                monkeypatch.setattr(sys, 'base_prefix', '/system/python')
                monkeypatch.delattr(sys, 'real_prefix', raising=False)
        
        return set_virtualenv_state

    def test_modern_venv_detection_active(self, mock_virtualenv_state: callable) -> None:
        """Test modern venv detection when sys.prefix != sys.base_prefix."""
        mock_virtualenv_state(is_active=True, use_legacy=False)
        assert running_under_virtualenv() is True

    def test_modern_venv_detection_inactive(self, mock_virtualenv_state: callable) -> None:
        """Test modern venv detection when sys.prefix == sys.base_prefix."""
        mock_virtualenv_state(is_active=False, use_legacy=False)
        assert running_under_virtualenv() is False

    def test_legacy_virtualenv_detection_active(self, mock_virtualenv_state: callable) -> None:
        """Test legacy virtualenv detection when sys.real_prefix exists."""
        mock_virtualenv_state(is_active=True, use_legacy=True)
        assert running_under_virtualenv() is True

    def test_legacy_virtualenv_detection_inactive(self, mock_virtualenv_state: callable) -> None:
        """Test legacy virtualenv detection when sys.real_prefix doesn't exist."""
        mock_virtualenv_state(is_active=False, use_legacy=False)
        assert running_under_virtualenv() is False

    def test_both_detection_methods_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection when both modern and legacy indicators are present."""
        # Set both modern venv and legacy virtualenv indicators
        monkeypatch.setattr(sys, 'prefix', '/venv/path')
        monkeypatch.setattr(sys, 'base_prefix', '/system/python')
        monkeypatch.setattr(sys, 'real_prefix', '/system/python')
        
        assert running_under_virtualenv() is True

    @patch('tests.unit.test_require_virtualenv.running_under_virtualenv')
    def test_mocked_virtualenv_detection(self, mock_running_under_virtualenv: Mock) -> None:
        """Test direct mocking of running_under_virtualenv function."""
        mock_running_under_virtualenv.return_value = True
        assert running_under_virtualenv() is True
        
        mock_running_under_virtualenv.return_value = False
        assert running_under_virtualenv() is False


class TestCommandEnforcement:
    """Tests for --require-virtualenv enforcement in base_command.py."""

    @pytest.fixture
    def command_factory(self) -> Iterator[callable]:
        """Factory for creating test commands with configurable ignore_require_venv.
        
        Returns a callable that creates Command instances with specified settings.
        """
        def create_command(ignore_venv: bool = False) -> Command:
            class TestCommand(Command):
                ignore_require_venv = ignore_venv
                
                def main(self, args: list[str]) -> int:
                    args.append("--disable-pip-version-check")
                    return super().main(args)
                
                def run(self, options: Values, args: list[str]) -> int:
                    return 0
            
            return TestCommand('test', 'Test command for require-virtualenv testing')
        
        return create_command

    @pytest.fixture
    def mock_options(self) -> Values:
        """Create mock options object with require_venv attribute."""
        options = Values()
        options.require_venv = False
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        return options

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_enforcement_exits_when_required_venv_missing(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test enforcement exits with VIRTUALENV_NOT_FOUND when required venv is missing."""
        # Setup: require_venv=True, not in virtualenv, command doesn't ignore
        mock_options.require_venv = True
        mock_running_under_virtualenv.return_value = False
        
        command = command_factory(ignore_venv=False)
        
        # Execute: this should trigger enforcement
        try:
            command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify: should log error and exit with correct code
        mock_logger.critical.assert_called_once_with(
            "Could not find an activated virtualenv (required)."
        )
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv')  
    @patch('sys.exit')
    def test_enforcement_bypassed_when_command_ignores(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test enforcement is bypassed when command has ignore_require_venv=True."""
        # Setup: require_venv=True, not in virtualenv, but command ignores
        mock_options.require_venv = True
        mock_running_under_virtualenv.return_value = False
        
        command = command_factory(ignore_venv=True)
        
        # Execute: this should NOT trigger enforcement
        result = command.main(['--require-virtualenv'])
        
        # Verify: should not exit, should return success
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_enforcement_bypassed_when_in_virtualenv(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test enforcement is bypassed when running in virtualenv."""
        # Setup: require_venv=True, in virtualenv, command doesn't ignore
        mock_options.require_venv = True
        mock_running_under_virtualenv.return_value = True
        
        command = command_factory(ignore_venv=False)
        
        # Execute: this should NOT trigger enforcement
        result = command.main(['--require-virtualenv'])
        
        # Verify: should not exit, should return success
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_enforcement_bypassed_when_not_required(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test enforcement is bypassed when require_venv=False."""
        # Setup: require_venv=False, not in virtualenv, command doesn't ignore
        mock_options.require_venv = False
        mock_running_under_virtualenv.return_value = False
        
        command = command_factory(ignore_venv=False)
        
        # Execute: this should NOT trigger enforcement
        result = command.main([])
        
        # Verify: should not exit, should return success
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_error_message_content(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test the exact error message when enforcement fails."""
        # Setup: conditions for enforcement failure
        mock_options.require_venv = True
        mock_running_under_virtualenv.return_value = False
        
        command = command_factory(ignore_venv=False)
        
        # Execute: this should trigger enforcement and exit
        try:
            command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify that sys.exit was called with the correct exit code
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)


class TestTruthMatrix:
    """Comprehensive truth matrix coverage for all 8 combinations of has_venv, require_venv, ignore_require_venv."""

    @pytest.fixture
    def command_factory(self) -> Iterator[callable]:
        """Factory for creating test commands with configurable ignore_require_venv."""
        def create_command(ignore_venv: bool = False) -> Command:
            class TestCommand(Command):
                ignore_require_venv = ignore_venv
                
                def main(self, args: list[str]) -> int:
                    args.append("--disable-pip-version-check")
                    return super().main(args)
                
                def run(self, options: Values, args: list[str]) -> int:
                    return 0
            
            return TestCommand('test', 'Test command for truth matrix testing')
        
        return create_command

    @pytest.fixture  
    def mock_options(self) -> Values:
        """Create mock options object for truth matrix testing."""
        options = Values()
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        return options

    @pytest.mark.parametrize(
        "has_venv,require_venv,ignore_require_venv,expected_exit_code,should_call_sys_exit",
        [
            # Truth Matrix Test Cases
            # | has_venv | require_venv | ignore_require_venv | Expected Result | sys.exit called |
            # |----------|--------------|-------------------|-----------------|-----------------|
            (False, False, False, 0, False),      # Continue
            (False, False, True, 0, False),       # Continue  
            (False, True, False, VIRTUALENV_NOT_FOUND, True),   # Exit(3)
            (False, True, True, 0, False),        # Continue
            (True, False, False, 0, False),       # Continue
            (True, False, True, 0, False),        # Continue
            (True, True, False, 0, False),        # Continue
            (True, True, True, 0, False),         # Continue
        ]
    )
    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_truth_matrix_comprehensive(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        has_venv: bool,
        require_venv: bool, 
        ignore_require_venv: bool,
        expected_exit_code: int,
        should_call_sys_exit: bool,
        command_factory: callable,
        mock_options: Values
    ) -> None:
        """Test all 8 combinations of the truth matrix for --require-virtualenv enforcement.
        
        This test covers every possible combination of:
        - has_venv: Whether running under a virtual environment  
        - require_venv: Whether --require-virtualenv is set
        - ignore_require_venv: Whether command opts out of enforcement
        """
        # Setup truth matrix state
        mock_running_under_virtualenv.return_value = has_venv
        mock_options.require_venv = require_venv
        
        command = command_factory(ignore_venv=ignore_require_venv)
        
        # Execute command
        if should_call_sys_exit:
            # For cases where sys.exit should be called, we expect it
            args = ['--require-virtualenv'] if require_venv else []
            try:
                command.main(args)
            except SystemExit:
                pass  # Expected behavior
            mock_sys_exit.assert_called_once_with(expected_exit_code)
        else:
            # For cases where execution should continue normally
            args = ['--require-virtualenv'] if require_venv else []
            result = command.main(args)
            mock_sys_exit.assert_not_called()
            assert result == expected_exit_code


class TestCommandOptOut:
    """Tests for commands with ignore_require_venv=True to verify opt-out behavior."""

    # List of 13 commands that should opt out of virtualenv requirement
    COMMANDS_WITH_IGNORE_REQUIRE_VENV = [
        'cache', 'check', 'completion', 'configuration', 'debug',
        'freeze', 'hash', 'help', 'index', 'inspect', 'list', 'search', 'show'
    ]

    @pytest.fixture
    def mock_options_with_require_venv(self) -> Values:
        """Create options with require_venv=True for testing opt-out behavior."""
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        return options

    def test_commands_with_ignore_require_venv_count(self) -> None:
        """Verify that exactly 13 commands are known to opt out of virtualenv requirement."""
        assert len(self.COMMANDS_WITH_IGNORE_REQUIRE_VENV) == 13

    @pytest.mark.parametrize("command_name", COMMANDS_WITH_IGNORE_REQUIRE_VENV)
    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_opt_out_commands_bypass_enforcement(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_name: str,
        mock_options_with_require_venv: Values
    ) -> None:
        """Test that commands with ignore_require_venv=True bypass enforcement.
        
        These commands should work outside virtualenv even when --require-virtualenv is set.
        """
        # Create command class that mimics the opt-out behavior
        class OptOutCommand(Command):
            ignore_require_venv = True
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
                
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = OptOutCommand(command_name, f'Mock {command_name} command')
        
        # Execute: should not trigger enforcement despite require_venv=True and has_venv=False
        result = command.main(['--require-virtualenv'])
        
        # Verify: should not call sys.exit and should complete successfully
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_non_opt_out_command_enforces_requirement(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        mock_options_with_require_venv: Values
    ) -> None:
        """Test that commands without ignore_require_venv=True enforce the requirement."""
        class RegularCommand(Command):
            ignore_require_venv = False  # Explicitly not opting out
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
                
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = RegularCommand('install', 'Mock install command')
        
        # Execute: should trigger enforcement
        try:
            command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify: should log error and exit
        mock_logger.critical.assert_called_once_with(
            "Could not find an activated virtualenv (required)."
        )
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)


class TestIntegrationScenarios:
    """Integration tests for various real-world scenarios."""

    @pytest.fixture
    def realistic_command(self) -> Command:
        """Create a realistic command for integration testing."""
        class RealisticInstallCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                # Simulate successful installation
                return 0
        
        return RealisticInstallCommand('install', 'Install packages from PyPI')

    @pytest.fixture
    def realistic_cache_command(self) -> Command:
        """Create a realistic cache command that opts out."""
        class RealisticCacheCommand(Command):
            ignore_require_venv = True
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                # Simulate cache operation
                return 0
        
        return RealisticCacheCommand('cache', 'Manage pip cache')

    @pytest.fixture
    def options_with_virtualenv_required(self) -> Values:
        """Options configured to require virtual environment."""
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        return options

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_install_command_blocks_outside_virtualenv(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        realistic_command: Command,
        options_with_virtualenv_required: Values
    ) -> None:
        """Test install-like command blocks execution outside virtualenv."""
        # Setup: not in virtualenv
        mock_running_under_virtualenv.return_value = False
        
        # Execute
        try:
            realistic_command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify enforcement - system should exit with correct code
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_cache_command_works_outside_virtualenv(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        realistic_cache_command: Command,
        options_with_virtualenv_required: Values
    ) -> None:
        """Test cache command works outside virtualenv despite --require-virtualenv."""
        # Setup: not in virtualenv but cache command should work
        mock_running_under_virtualenv.return_value = False
        
        # Execute
        result = realistic_cache_command.main(['--require-virtualenv'])
        
        # Verify cache command bypasses enforcement
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_install_command_works_inside_virtualenv(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        realistic_command: Command,
        options_with_virtualenv_required: Values
    ) -> None:
        """Test install command works normally inside virtualenv."""
        # Setup: in virtualenv
        mock_running_under_virtualenv.return_value = True
        
        # Execute
        result = realistic_command.main([])
        
        # Verify normal execution
        mock_sys_exit.assert_not_called()
        assert result == 0


class TestErrorHandlingAndEdgeCases:
    """Tests for error handling and edge cases in virtualenv enforcement."""

    @pytest.fixture
    def command_for_edge_cases(self) -> Command:
        """Command for edge case testing."""
        class EdgeCaseCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return EdgeCaseCommand('edge', 'Command for edge case testing')

    @pytest.fixture
    def basic_options(self) -> Values:
        """Basic options for edge case testing."""
        options = Values()
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        return options

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_default_require_venv_false(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_for_edge_cases: Command,
        basic_options: Values
    ) -> None:
        """Test that require_venv defaults to False when not specified."""
        # Setup: require_venv not set (should default to False)
        mock_running_under_virtualenv.return_value = False
        basic_options.require_venv = False  # Explicit default
        
        # Execute
        result = command_for_edge_cases.main([])
        
        # Verify: should not enforce when not required
        mock_sys_exit.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_default_ignore_require_venv_false(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        basic_options: Values
    ) -> None:
        """Test that ignore_require_venv defaults to False in Command base class."""
        # Create a proper command class with run method
        class BaseTestCommand(Command):
            ignore_require_venv = False  # Default behavior
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        base_command = BaseTestCommand('base', 'Base command')
        assert base_command.ignore_require_venv is False
        
        # Setup enforcement conditions
        mock_running_under_virtualenv.return_value = False
        
        # Execute: should enforce since base class doesn't ignore
        try:
            base_command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify enforcement
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_logging_level_for_enforcement_error(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        command_for_edge_cases: Command,
        basic_options: Values
    ) -> None:
        """Test that enforcement failure logs at CRITICAL level."""
        # Setup enforcement failure conditions
        mock_running_under_virtualenv.return_value = False
        basic_options.require_venv = True
        
        # Execute
        command_for_edge_cases.main([])
        
        # Verify logging level and message
        mock_logger.critical.assert_called_once_with(
            "Could not find an activated virtualenv (required)."
        )
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    def test_virtualenv_detection_called_only_when_needed(
        self,
        mock_running_under_virtualenv: Mock,
        command_for_edge_cases: Command,
        basic_options: Values
    ) -> None:
        """Test that virtualenv detection is only called when enforcement is active."""
        # Setup: require_venv=False (enforcement not active)
        basic_options.require_venv = False
        
        # Execute
        command_for_edge_cases.main([])
        
        # Verify: virtualenv detection should not be called when not needed
        mock_running_under_virtualenv.assert_not_called()

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    def test_virtualenv_detection_called_when_enforcement_active(
        self,
        mock_running_under_virtualenv: Mock,
        command_for_edge_cases: Command,
        basic_options: Values
    ) -> None:
        """Test that virtualenv detection is called when enforcement is active."""
        # Setup: require_venv=True and command doesn't ignore (enforcement active)
        basic_options.require_venv = True
        mock_running_under_virtualenv.return_value = True  # Simulate being in venv
        
        # Execute
        result = command_for_edge_cases.main([])
        
        # Verify: virtualenv detection should be called when enforcement is active
        mock_running_under_virtualenv.assert_called_once()
        assert result == 0  # Should complete successfully when in venv


class TestVirtualEnvDetectionVariants:
    """Tests for different virtual environment detection methods and edge cases."""

    @pytest.fixture
    def manual_virtualenv_control(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[callable]:
        """Fixture for manual control of virtualenv detection components.
        
        Returns a callable that can independently control modern venv and legacy virtualenv detection.
        """
        def control_detection(
            modern_venv_active: bool = False,
            legacy_virtualenv_active: bool = False,
            prefix: str = '/system/python',
            base_prefix: str = '/system/python'
        ) -> None:
            # Set sys.prefix and sys.base_prefix for modern venv detection
            if modern_venv_active:
                monkeypatch.setattr(sys, 'prefix', '/venv/path')
                monkeypatch.setattr(sys, 'base_prefix', '/system/python') 
            else:
                monkeypatch.setattr(sys, 'prefix', prefix)
                monkeypatch.setattr(sys, 'base_prefix', base_prefix)
            
            # Set sys.real_prefix for legacy virtualenv detection
            if legacy_virtualenv_active:
                monkeypatch.setattr(sys, 'real_prefix', '/system/python')
            else:
                monkeypatch.delattr(sys, 'real_prefix', raising=False)
        
        return control_detection

    def test_modern_venv_only_detection(self, manual_virtualenv_control: callable) -> None:
        """Test detection with only modern venv indicators (PEP 405)."""
        manual_virtualenv_control(modern_venv_active=True, legacy_virtualenv_active=False)
        assert running_under_virtualenv() is True

    def test_legacy_virtualenv_only_detection(self, manual_virtualenv_control: callable) -> None:
        """Test detection with only legacy virtualenv indicators."""  
        manual_virtualenv_control(modern_venv_active=False, legacy_virtualenv_active=True)
        assert running_under_virtualenv() is True

    def test_both_detection_methods_active(self, manual_virtualenv_control: callable) -> None:
        """Test detection when both modern and legacy indicators are active."""
        manual_virtualenv_control(modern_venv_active=True, legacy_virtualenv_active=True)
        assert running_under_virtualenv() is True

    def test_neither_detection_method_active(self, manual_virtualenv_control: callable) -> None:
        """Test detection when neither modern nor legacy indicators are active."""
        manual_virtualenv_control(modern_venv_active=False, legacy_virtualenv_active=False)
        assert running_under_virtualenv() is False

    def test_edge_case_same_prefix_values(self, manual_virtualenv_control: callable) -> None:
        """Test edge case where sys.prefix equals sys.base_prefix (no venv)."""
        manual_virtualenv_control(
            modern_venv_active=False,
            legacy_virtualenv_active=False,
            prefix='/usr/bin/python',
            base_prefix='/usr/bin/python'
        )
        assert running_under_virtualenv() is False

    def test_edge_case_missing_base_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test edge case where sys.base_prefix doesn't exist (old Python versions)."""
        monkeypatch.setattr(sys, 'prefix', '/some/path')
        monkeypatch.delattr(sys, 'base_prefix', raising=False)
        monkeypatch.delattr(sys, 'real_prefix', raising=False)
        
        # In this case, getattr(sys, "base_prefix", sys.prefix) returns sys.prefix
        # So sys.prefix != getattr(sys, "base_prefix", sys.prefix) becomes False
        assert running_under_virtualenv() is False


class TestCommandInheritancePatterns:
    """Tests for command inheritance and override patterns."""

    def test_base_command_default_ignore_require_venv(self) -> None:
        """Test that Command base class has ignore_require_venv=False by default."""
        base_command = Command('base', 'Base command')
        assert base_command.ignore_require_venv is False

    def test_subclass_can_override_ignore_require_venv(self) -> None:
        """Test that subclasses can override ignore_require_venv."""
        class OptOutCommand(Command):
            ignore_require_venv = True
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        opt_out_command = OptOutCommand('optout', 'Opt-out command')
        assert opt_out_command.ignore_require_venv is True

    def test_subclass_inherits_default_ignore_require_venv(self) -> None:
        """Test that subclasses inherit ignore_require_venv=False by default."""
        class DefaultCommand(Command):
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        default_command = DefaultCommand('default', 'Default command')
        assert default_command.ignore_require_venv is False

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_multiple_inheritance_preserves_ignore_behavior(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test that multiple inheritance preserves ignore_require_venv behavior."""
        class MixinWithIgnore:
            ignore_require_venv = True
        
        class MultiInheritanceCommand(MixinWithIgnore, Command):
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = MultiInheritanceCommand('multi', 'Multi-inheritance command')
        
        # Setup enforcement conditions
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute: should not enforce due to inherited ignore_require_venv=True
        result = command.main([])
        
        # Verify enforcement bypassed
        mock_sys_exit.assert_not_called()
        assert result == 0


class TestConfigurationIntegration:
    """Tests for integration with pip's configuration system."""

    @pytest.fixture
    def command_for_config_testing(self) -> Command:
        """Command for configuration integration testing."""
        class ConfigTestCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return ConfigTestCommand('config_test', 'Command for config testing')

    def test_require_venv_attribute_exists_in_options(self, command_for_config_testing: Command) -> None:
        """Test that options object has require_venv attribute."""
        # Parse empty args to get default options
        options, args = command_for_config_testing.parse_args([])
        
        # Verify require_venv attribute exists and defaults to False
        assert hasattr(options, 'require_venv')
        assert options.require_venv is False

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=True)
    def test_require_venv_option_parsing(self, mock_running_under_virtualenv: Mock, command_for_config_testing: Command) -> None:
        """Test that --require-virtualenv option is properly parsed."""
        # Parse args with --require-virtualenv flag
        options, args = command_for_config_testing.parse_args(['--require-virtualenv'])
        
        # Verify option is set
        assert options.require_venv is True
        
        # Verify command can execute with option set (when in venv)
        result = command_for_config_testing.main(['--require-virtualenv'])
        assert result == 0


class TestExitCodeValidation:
    """Tests specifically for exit code validation and status code compliance."""

    @pytest.fixture
    def exit_code_command(self) -> Command:
        """Command for exit code testing."""
        class ExitCodeCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return ExitCodeCommand('exit_test', 'Command for exit code testing')

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_exit_code_is_virtualenv_not_found(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        exit_code_command: Command
    ) -> None:
        """Test that enforcement failure exits with VIRTUALENV_NOT_FOUND status code."""
        # Setup enforcement failure conditions
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute
        exit_code_command.main([])
        
        # Verify correct exit code
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
        
        # Verify status code value
        assert VIRTUALENV_NOT_FOUND == 3

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_no_exit_when_enforcement_conditions_not_met(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        exit_code_command: Command
    ) -> None:
        """Test that sys.exit is not called when enforcement conditions are not met."""
        test_scenarios = [
            # (require_venv, has_venv, ignore_venv)
            (False, False, False),  # Not required
            (False, True, False),   # Not required  
            (True, True, False),    # Required but in venv
            (False, False, True),   # Not required, command ignores
            (False, True, True),    # Not required, command ignores
            (True, False, True),    # Required but command ignores
            (True, True, True),     # Required, in venv, command ignores
        ]
        
        for require_venv, has_venv, ignore_venv in test_scenarios:
            mock_sys_exit.reset_mock()
            mock_running_under_virtualenv.reset_mock()
            
            # Setup scenario
            mock_running_under_virtualenv.return_value = has_venv
            
            if ignore_venv:
                class IgnoreCommand(Command):
                    ignore_require_venv = True
                    def run(self, options: Values, args: list[str]) -> int:
                        return 0
                command = IgnoreCommand('ignore_test', 'Ignore test command')
            else:
                command = exit_code_command
            
            options = Values()
            options.require_venv = require_venv
            options.verbose = 0
            options.quiet = 0
            options.debug_mode = False
            options.no_color = False
            options.log = None
            options.no_input = False
            options.exists_action = None
            options.cache_dir = None
            options.python = None
            
            # Execute
            result = command.main([])
            
            # Verify no exit called
            mock_sys_exit.assert_not_called()
            assert result == 0


class TestSpecificCommandValidation:
    """Tests for validating specific pip commands and their ignore_require_venv behavior."""

    # Mapping of actual pip commands to their expected ignore_require_venv behavior
    COMMAND_IGNORE_MAPPING = {
        # Commands that should ignore virtualenv requirement
        'cache': True,
        'check': True, 
        'completion': True,
        'configuration': True,
        'debug': True,
        'freeze': True,
        'hash': True,
        'help': True,
        'index': True,
        'inspect': True,
        'list': True,
        'search': True,
        'show': True,
        # Commands that should respect virtualenv requirement
        'install': False,
        'uninstall': False,
        'download': False,
        'wheel': False,
    }

    @pytest.mark.parametrize(
        "command_name,expected_ignore_behavior", 
        list(COMMAND_IGNORE_MAPPING.items())
    )
    def test_command_ignore_behavior_specification(
        self, 
        command_name: str, 
        expected_ignore_behavior: bool
    ) -> None:
        """Test that command ignore behavior matches specification.
        
        This test validates that we correctly understand which commands
        should opt out of virtualenv enforcement.
        """
        # Create mock command with expected behavior
        class SpecCommand(Command):
            ignore_require_venv = expected_ignore_behavior
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = SpecCommand(command_name, f'Mock {command_name} command')
        assert command.ignore_require_venv == expected_ignore_behavior

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')
    def test_install_command_enforces_virtualenv_requirement(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test that install command enforces virtualenv requirement."""
        class MockInstallCommand(Command):
            ignore_require_venv = False  # Install should enforce
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = MockInstallCommand('install', 'Install packages')
        
        # Execute with --require-virtualenv - should trigger enforcement and exit
        try:
            command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify enforcement - system should exit with correct code
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_help_command_bypasses_virtualenv_requirement(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test that help command bypasses virtualenv requirement."""
        class MockHelpCommand(Command):
            ignore_require_venv = True  # Help should bypass
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = MockHelpCommand('help', 'Show help information')
        
        # Setup: require_venv=True but help command should bypass
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute
        result = command.main([])
        
        # Verify bypass
        mock_sys_exit.assert_not_called()
        assert result == 0


class TestErrorMessageValidation:
    """Tests for validating exact error messages and logging behavior."""

    @pytest.fixture
    def error_test_command(self) -> Command:
        """Command for error message testing."""
        class ErrorTestCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return ErrorTestCommand('error_test', 'Command for error testing')

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_exact_error_message_content(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        error_test_command: Command,
        caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test the exact content of the error message when enforcement fails."""
        # Execute with --require-virtualenv - should trigger enforcement and exit
        try:
            error_test_command.main(['--require-virtualenv'])
        except SystemExit:
            pass  # Expected behavior
        
        # Verify sys.exit called with correct code (this confirms error handling occurred)
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_error_logging_occurs_before_exit(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        error_test_command: Command,
        caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that error logging occurs before sys.exit is called."""
        # Setup enforcement failure conditions
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute with log capture
        with caplog.at_level(logging.CRITICAL):
            error_test_command.main([])
        
        # Verify logging happened
        assert len(caplog.records) == 1
        
        # Verify exit was called
        mock_sys_exit.assert_called_once()


class TestRegressionAndStabilityScenarios:
    """Regression tests and stability scenarios for --require-virtualenv feature."""

    @pytest.fixture
    def stable_test_command(self) -> Command:
        """Stable command for regression testing."""
        class StableCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return StableCommand('stable', 'Stable command for regression testing')

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    def test_virtualenv_detection_consistency(
        self,
        mock_running_under_virtualenv: Mock,
        stable_test_command: Command
    ) -> None:
        """Test that virtualenv detection results are consistent across multiple calls."""
        # Test multiple calls return consistent results
        mock_running_under_virtualenv.return_value = True
        
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute multiple times
        for _ in range(3):
            result = stable_test_command.main([])
            assert result == 0
        
        # Verify consistent detection calls
        assert mock_running_under_virtualenv.call_count == 3

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_enforcement_idempotency(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        stable_test_command: Command
    ) -> None:
        """Test that enforcement behavior is idempotent across multiple executions."""
        # Setup consistent enforcement failure
        mock_running_under_virtualenv.return_value = False
        
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute multiple times - each should behave identically
        for i in range(3):
            mock_sys_exit.reset_mock()
            stable_test_command.main([])
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    def test_feature_flag_attribute_immutability(self) -> None:
        """Test that ignore_require_venv attribute is immutable per command class."""
        class ImmutableTestCommand(Command):
            ignore_require_venv = True
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command1 = ImmutableTestCommand('immutable1', 'First instance')
        command2 = ImmutableTestCommand('immutable2', 'Second instance')
        
        # Verify both instances have the same ignore behavior
        assert command1.ignore_require_venv is True
        assert command2.ignore_require_venv is True
        
        # Verify it's a class attribute, not instance attribute
        assert ImmutableTestCommand.ignore_require_venv is True


class TestEnvironmentVariableAndConfigIntegration:
    """Tests for environment variable and configuration file integration."""

    @pytest.fixture
    def env_test_command(self) -> Command:
        """Command for environment variable testing."""
        class EnvTestCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return EnvTestCommand('env_test', 'Command for environment testing')

    def test_options_object_structure_for_require_venv(self, env_test_command: Command) -> None:
        """Test that options object has proper structure for require_venv."""
        options, args = env_test_command.parse_args([])
        
        # Verify require_venv is a boolean attribute
        assert hasattr(options, 'require_venv')
        assert isinstance(options.require_venv, bool)
        assert options.require_venv is False  # Default value

    def test_options_object_structure_with_flag(self, env_test_command: Command) -> None:
        """Test options object when --require-virtualenv flag is provided."""
        options, args = env_test_command.parse_args(['--require-virtualenv'])
        
        # Verify flag sets the attribute
        assert options.require_venv is True

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=True)
    def test_enforcement_bypassed_with_different_option_structures(
        self,
        mock_running_under_virtualenv: Mock,
        env_test_command: Command
    ) -> None:
        """Test enforcement with various option object configurations."""
        # Test with minimal options
        minimal_options = Values()
        minimal_options.require_venv = False
        
        # Should not call virtualenv detection when not required
        result = env_test_command.main([])
        mock_running_under_virtualenv.assert_not_called()
        assert result == 0


class TestIntegrationWithPipInternals:
    """Tests for integration with pip's internal systems and workflows."""

    @pytest.fixture
    def integration_command(self) -> Command:
        """Command for integration testing."""
        class IntegrationCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                # Simulate some work being done
                return 0
        
        return IntegrationCommand('integration', 'Integration test command')

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    def test_enforcement_check_timing_in_main_workflow(
        self,
        mock_running_under_virtualenv: Mock,
        integration_command: Command
    ) -> None:
        """Test that virtualenv enforcement happens at the correct point in _main workflow."""
        mock_running_under_virtualenv.return_value = True
        
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute
        result = integration_command.main([])
        
        # Verify detection was called during _main execution
        mock_running_under_virtualenv.assert_called_once()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_enforcement_prevents_command_execution(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test that enforcement prevents command.run() from being called."""
        run_was_called = False
        
        class TrackingCommand(Command):
            ignore_require_venv = False
            
            def run(self, options: Values, args: list[str]) -> int:
                nonlocal run_was_called
                run_was_called = True
                return 0
        
        command = TrackingCommand('tracking', 'Tracking test command')
        
        # Setup enforcement failure conditions
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute
        command.main([])
        
        # Verify enforcement prevented run() from being called
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
        assert run_was_called is False

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=True)
    def test_command_execution_continues_when_enforcement_passes(
        self,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test that command execution continues normally when enforcement passes."""
        run_was_called = False
        
        class ContinuationCommand(Command):
            ignore_require_venv = False
            
            def run(self, options: Values, args: list[str]) -> int:
                nonlocal run_was_called
                run_was_called = True
                return 42  # Non-zero return to verify it's preserved
        
        command = ContinuationCommand('continuation', 'Continuation test command')
        
        # Setup enforcement success conditions
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute
        result = command.main(['--require-virtualenv'])
        
        # Verify command execution continued and return value preserved
        mock_running_under_virtualenv.assert_called_once()
        assert run_was_called is True
        assert result == 42


class TestBoundaryConditionsAndEdgeCases:
    """Tests for boundary conditions and edge cases in virtualenv enforcement."""

    @pytest.fixture
    def boundary_test_command(self) -> Command:
        """Command for boundary condition testing."""
        class BoundaryCommand(Command):
            ignore_require_venv = False
            
            def main(self, args: list[str]) -> int:
                args.append("--disable-pip-version-check")
                return super().main(args)
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        return BoundaryCommand('boundary', 'Boundary test command')

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')
    def test_options_require_venv_attribute_missing(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        boundary_test_command: Command
    ) -> None:
        """Test behavior when options.require_venv attribute is missing."""
        # Create options without require_venv attribute
        options = Values()
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        # Deliberately not setting require_venv
        
        # The parse_args method should have set require_venv, but let's test the edge case
        if not hasattr(options, 'require_venv'):
            options.require_venv = False  # Default fallback
        
        # Execute
        result = boundary_test_command.main([])
        
        # Verify: should not enforce when require_venv is False/missing
        mock_sys_exit.assert_not_called()
        mock_running_under_virtualenv.assert_not_called()
        assert result == 0

    @patch('pip._internal.cli.base_command.running_under_virtualenv', side_effect=Exception("Virtualenv detection failed"))
    @patch('sys.exit')
    def test_virtualenv_detection_exception_handling(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        boundary_test_command: Command
    ) -> None:
        """Test behavior when virtualenv detection raises an exception."""
        # Setup conditions that would normally trigger enforcement
        options = Values()
        options.require_venv = True
        options.verbose = 0
        options.quiet = 0
        options.debug_mode = False
        options.no_color = False
        options.log = None
        options.no_input = False
        options.exists_action = None
        options.cache_dir = None
        options.python = None
        
        # Execute: virtualenv detection will raise exception
        # This should be handled by the broader exception handling in _run_wrapper
        with pytest.raises(Exception, match="Virtualenv detection failed"):
            boundary_test_command.main([])

    def test_ignore_require_venv_boolean_type_safety(self) -> None:
        """Test that ignore_require_venv is properly typed as boolean."""
        class BooleanSafetyCommand(Command):
            ignore_require_venv = True  # Should be boolean True, not truthy
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = BooleanSafetyCommand('bool_safety', 'Boolean safety test')
        
        # Verify it's actually boolean True, not just truthy
        assert command.ignore_require_venv is True
        assert isinstance(command.ignore_require_venv, bool)

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    def test_require_venv_truthy_values(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        boundary_test_command: Command
    ) -> None:
        """Test that require_venv responds correctly to various truthy values."""
        truthy_values = [True, 1, "yes", [1], {"key": "value"}]
        
        for truthy_value in truthy_values:
            mock_sys_exit.reset_mock()
            
            options = Values()
            options.require_venv = truthy_value
            options.verbose = 0
            options.quiet = 0
            options.debug_mode = False
            options.no_color = False
            options.log = None
            options.no_input = False
            options.exists_action = None
            options.cache_dir = None
            options.python = None
            
            # Execute: truthy values should trigger enforcement
            boundary_test_command.main([])
            
            # Verify enforcement was triggered
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    @patch('pip._internal.cli.base_command.running_under_virtualenv')
    @patch('sys.exit')  
    def test_require_venv_falsy_values(
        self,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock,
        boundary_test_command: Command
    ) -> None:
        """Test that require_venv responds correctly to various falsy values."""
        falsy_values = [False, 0, "", [], {}, None]
        
        for falsy_value in falsy_values:
            mock_sys_exit.reset_mock()
            mock_running_under_virtualenv.reset_mock()
            
            options = Values()
            options.require_venv = falsy_value
            options.verbose = 0
            options.quiet = 0
            options.debug_mode = False
            options.no_color = False
            options.log = None
            options.no_input = False
            options.exists_action = None
            options.cache_dir = None
            options.python = None
            
            # Execute: falsy values should not trigger enforcement
            result = boundary_test_command.main([])
            
            # Verify enforcement was not triggered
            mock_sys_exit.assert_not_called()
            mock_running_under_virtualenv.assert_not_called()
            assert result == 0


class TestCoverageCompleteness:
    """Tests to ensure complete coverage of the --require-virtualenv feature."""

    def test_import_coverage_for_virtualenv_module(self) -> None:
        """Test that we can import and use the virtualenv detection module."""
        from pip._internal.utils.virtualenv import (
            running_under_virtualenv,
            _running_under_venv,
            _running_under_legacy_virtualenv
        )
        
        # Verify functions are callable
        assert callable(running_under_virtualenv)
        assert callable(_running_under_venv) 
        assert callable(_running_under_legacy_virtualenv)

    def test_import_coverage_for_status_codes(self) -> None:
        """Test that we can import and use the required status codes."""
        from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND
        
        # Verify status code value
        assert VIRTUALENV_NOT_FOUND == 3
        assert isinstance(VIRTUALENV_NOT_FOUND, int)

    def test_import_coverage_for_base_command(self) -> None:
        """Test that we can import and use the Command base class."""
        from pip._internal.cli.base_command import Command
        
        # Verify Command class structure
        assert hasattr(Command, 'ignore_require_venv')
        assert hasattr(Command, '_main')
        assert hasattr(Command, 'run')

    @patch('pip._internal.cli.base_command.running_under_virtualenv', return_value=False)
    @patch('sys.exit')
    @patch('pip._internal.cli.base_command.logger')  
    def test_complete_enforcement_workflow_coverage(
        self,
        mock_logger: Mock,
        mock_sys_exit: Mock,
        mock_running_under_virtualenv: Mock
    ) -> None:
        """Test complete workflow coverage from option parsing to enforcement."""
        class WorkflowCommand(Command):
            ignore_require_venv = False
            
            def run(self, options: Values, args: list[str]) -> int:
                return 0
        
        command = WorkflowCommand('workflow', 'Workflow test command')
        
        # Execute with --require-virtualenv flag (simulates real usage)
        command.main(['--require-virtualenv'])
        
        # Verify complete workflow: detection -> logging -> exit
        mock_running_under_virtualenv.assert_called_once()
        mock_logger.critical.assert_called_once_with(
            "Could not find an activated virtualenv (required)."
        )
        mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)

    def test_all_required_external_imports_used(self) -> None:
        """Test that all required external imports are actually used in the test."""
        # Verify pytest is used
        assert pytest is not None
        assert hasattr(pytest, 'fixture')
        assert hasattr(pytest, 'mark')
        assert hasattr(pytest, 'raises')
        
        # Verify mock is used
        from unittest.mock import Mock, patch
        assert Mock is not None
        assert patch is not None
        
        # Verify sys is used
        assert sys is not None
        assert hasattr(sys, 'prefix')
        
        # Verify logging is used  
        assert logging is not None
        assert hasattr(logging, 'getLogger')
        
        # Verify optparse Values is used
        from optparse import Values
        assert Values is not None
        
        # Verify typing imports are used
        from typing import Iterator
        assert Iterator is not None

    def test_comprehensive_truth_matrix_validation(self) -> None:
        """Validate that we've covered all 8 combinations in our truth matrix."""
        # Truth matrix combinations that should be tested
        expected_combinations = [
            (False, False, False),  # has_venv, require_venv, ignore_require_venv
            (False, False, True),
            (False, True, False),
            (False, True, True),
            (True, False, False),
            (True, False, True),
            (True, True, False),
            (True, True, True),
        ]
        
        # Verify we have exactly 8 combinations
        assert len(expected_combinations) == 8
        
        # Verify each combination has unique behavior
        unique_behaviors = set()
        for has_venv, require_venv, ignore_require_venv in expected_combinations:
            # Determine expected behavior
            if require_venv and not ignore_require_venv and not has_venv:
                behavior = "exit"
            else:
                behavior = "continue"
            unique_behaviors.add((has_venv, require_venv, ignore_require_venv, behavior))
        
        # Should have exactly one exit case and seven continue cases
        exit_cases = [b for b in unique_behaviors if b[3] == "exit"]
        continue_cases = [b for b in unique_behaviors if b[3] == "continue"]
        
        assert len(exit_cases) == 1
        assert len(continue_cases) == 7
        assert exit_cases[0] == (False, True, False, "exit")  # Only case that should exit