"""
Comprehensive unit tests for pip's --require-virtualenv CLI option functionality.

Tests cover all truth matrix combinations of virtual environment detection,
require_venv flag, and ignore_require_venv attribute, validating the enforcement
logic in base_command.Command._main() method.
"""

from __future__ import annotations

import logging
import sys
from optparse import Values
from unittest.mock import Mock, patch

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND
from pip._internal.commands.check import CheckCommand
from pip._internal.commands.freeze import FreezeCommand
from pip._internal.commands.inspect import InspectCommand
from pip._internal.commands.list import ListCommand
from pip._internal.utils.virtualenv import running_under_virtualenv


class TestCommand(Command):
    """Test command for testing require_venv functionality."""
    
    def __init__(self, ignore_require_venv: bool = False):
        super().__init__("test", "Test command")
        self.ignore_require_venv = ignore_require_venv
        
    def run(self, options: Values, args: list[str]) -> int:
        """Simple run method that returns success."""
        return 0


@pytest.fixture
def mock_options():
    """Create a mock options object with require_venv attribute."""
    options = Mock(spec=Values)
    options.require_venv = False
    options.no_input = False
    options.exists_action = None
    options.cache_dir = None
    options.python = None
    options.verbose = 0
    options.quiet = 0
    options.debug_mode = False
    options.no_color = False
    options.log = None
    options.features_enabled = []
    return options


@pytest.fixture
def mock_virtualenv_detection(monkeypatch):
    """Fixture to control virtual environment detection state."""
    def _set_virtualenv_state(is_in_venv: bool):
        monkeypatch.setattr(
            "pip._internal.utils.virtualenv.running_under_virtualenv",
            lambda: is_in_venv
        )
    return _set_virtualenv_state


@pytest.fixture
def mock_sys_exit(monkeypatch):
    """Fixture to mock sys.exit calls."""
    exit_mock = Mock()
    monkeypatch.setattr(sys, "exit", exit_mock)
    return exit_mock


@pytest.fixture
def mock_logger(monkeypatch):
    """Fixture to mock logger.critical calls."""
    logger_mock = Mock()
    monkeypatch.setattr(
        "pip._internal.cli.base_command.logger.critical",
        logger_mock
    )
    return logger_mock


class TestRequireVirtualenvTruthMatrix:
    """Test all 8 combinations of the require_venv truth matrix."""
    
    @pytest.mark.parametrize("has_venv,require_venv,ignore_require_venv,should_exit", [
        # Case 1: has_venv=True, require_venv=True, ignore_require_venv=False
        # Should proceed normally (virtualenv found)
        (True, True, False, False),
        
        # Case 2: has_venv=True, require_venv=True, ignore_require_venv=True
        # Should proceed normally (ignore flag set)
        (True, True, True, False),
        
        # Case 3: has_venv=True, require_venv=False, ignore_require_venv=False
        # Should proceed normally (require_venv not set)
        (True, False, False, False),
        
        # Case 4: has_venv=True, require_venv=False, ignore_require_venv=True
        # Should proceed normally (require_venv not set)
        (True, False, True, False),
        
        # Case 5: has_venv=False, require_venv=True, ignore_require_venv=False
        # Should exit with VIRTUALENV_NOT_FOUND (requirement not met)
        (False, True, False, True),
        
        # Case 6: has_venv=False, require_venv=True, ignore_require_venv=True
        # Should proceed normally (ignore flag set)
        (False, True, True, False),
        
        # Case 7: has_venv=False, require_venv=False, ignore_require_venv=False
        # Should proceed normally (require_venv not set)
        (False, False, False, False),
        
        # Case 8: has_venv=False, require_venv=False, ignore_require_venv=True
        # Should proceed normally (require_venv not set)
        (False, False, True, False),
    ])
    def test_require_venv_truth_matrix(
        self, 
        has_venv: bool, 
        require_venv: bool, 
        ignore_require_venv: bool,
        should_exit: bool,
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test all combinations of require_venv, ignore_require_venv, and virtualenv detection."""
        # Setup test conditions
        mock_virtualenv_detection(has_venv)
        mock_options.require_venv = require_venv
        
        # Create test command with appropriate ignore_require_venv setting
        command = TestCommand(ignore_require_venv=ignore_require_venv)
        
        # Mock the run method to avoid actual execution
        with patch.object(command, 'run', return_value=0):
            with patch.object(command, 'parse_args', return_value=(mock_options, [])):
                with patch('pip._internal.cli.base_command.setup_logging'):
                    with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                        with patch('pip._internal.cli.base_command.tempdir_registry'):
                            with patch('pip._internal.cli.base_command.reconfigure'):
                                
                                if should_exit:
                                    # Test should trigger sys.exit
                                    command._main([])
                                    mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
                                    mock_logger.assert_called_once_with(
                                        "Could not find an activated virtualenv (required)."
                                    )
                                else:
                                    # Test should proceed normally
                                    result = command._main([])
                                    mock_sys_exit.assert_not_called()
                                    mock_logger.assert_not_called()
                                    # The run method should be called and return 0
                                    assert result == 0


class TestRequireVirtualenvErrorHandling:
    """Test error handling and messaging for require_venv functionality."""
    
    def test_require_venv_error_message(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that the correct error message is logged when virtualenv is not found."""
        # Setup: no virtualenv, require_venv=True, ignore_require_venv=False
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            
                            command._main([])
                            
                            # Verify the exact error message
                            mock_logger.assert_called_once_with(
                                "Could not find an activated virtualenv (required)."
                            )
    
    def test_require_venv_exit_code(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that the correct exit code is returned when virtualenv is not found."""
        # Setup: no virtualenv, require_venv=True, ignore_require_venv=False
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            
                            command._main([])
                            
                            # Verify the exit code is VIRTUALENV_NOT_FOUND (3)
                            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
                            assert VIRTUALENV_NOT_FOUND == 3
    
    def test_require_venv_logging_behavior(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        caplog
    ):
        """Test that critical logging occurs at the correct level."""
        # Setup: no virtualenv, require_venv=True, ignore_require_venv=False
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            with caplog.at_level(logging.CRITICAL):
                                
                                command._main([])
                                
                                # Check that a critical log message was recorded
                                assert "Could not find an activated virtualenv (required)." in caplog.text
                                assert caplog.records[0].levelname == "CRITICAL"


class TestCommandSpecificBypassBehavior:
    """Test commands that have ignore_require_venv=True bypass the virtualenv requirement."""
    
    @pytest.mark.parametrize("command_class", [
        ListCommand,
        CheckCommand,
        InspectCommand,
        FreezeCommand,
    ])
    def test_command_ignores_require_venv(
        self, 
        command_class,
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that commands with ignore_require_venv=True bypass the virtualenv check."""
        # Setup: no virtualenv, require_venv=True
        # These commands should still proceed normally due to ignore_require_venv=True
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = command_class("test", "Test command")
        
        # Verify the command has ignore_require_venv=True
        assert command.ignore_require_venv is True
        
        with patch.object(command, 'run', return_value=0):
            with patch.object(command, 'parse_args', return_value=(mock_options, [])):
                with patch('pip._internal.cli.base_command.setup_logging'):
                    with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                        with patch('pip._internal.cli.base_command.tempdir_registry'):
                            with patch('pip._internal.cli.base_command.reconfigure'):
                                
                                # Command should proceed normally despite no virtualenv
                                result = command._main([])
                                
                                # Should not exit or log error
                                mock_sys_exit.assert_not_called()
                                mock_logger.assert_not_called()
                                assert result == 0
    
    def test_regular_command_respects_require_venv(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that regular commands (ignore_require_venv=False) respect the virtualenv requirement."""
        # Setup: no virtualenv, require_venv=True
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        # Use a regular command that doesn't ignore require_venv
        command = TestCommand(ignore_require_venv=False)
        
        # Verify the command respects require_venv
        assert command.ignore_require_venv is False
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            
                            # Command should exit with error
                            command._main([])
                            
                            # Should exit with VIRTUALENV_NOT_FOUND and log error
                            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
                            mock_logger.assert_called_once_with(
                                "Could not find an activated virtualenv (required)."
                            )


class TestVirtualenvDetectionIntegration:
    """Test integration with the virtualenv detection function."""
    
    def test_running_under_virtualenv_function_called(
        self, 
        mock_options: Mock,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that running_under_virtualenv() is actually called during the check."""
        # Setup: require_venv=True, ignore_require_venv=False
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            with patch('pip._internal.cli.base_command.running_under_virtualenv') as mock_venv:
                                
                                # Mock virtualenv detection to return False
                                mock_venv.return_value = False
                                
                                command._main([])
                                
                                # Verify that running_under_virtualenv was called
                                mock_venv.assert_called_once()
                                
                                # Should exit with error
                                mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
    
    def test_virtualenv_detection_with_venv_present(
        self, 
        mock_options: Mock,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test behavior when virtualenv is detected."""
        # Setup: require_venv=True, ignore_require_venv=False
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'run', return_value=0):
            with patch.object(command, 'parse_args', return_value=(mock_options, [])):
                with patch('pip._internal.cli.base_command.setup_logging'):
                    with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                        with patch('pip._internal.cli.base_command.tempdir_registry'):
                            with patch('pip._internal.cli.base_command.reconfigure'):
                                with patch('pip._internal.cli.base_command.running_under_virtualenv') as mock_venv:
                                    
                                    # Mock virtualenv detection to return True
                                    mock_venv.return_value = True
                                    
                                    result = command._main([])
                                    
                                    # Verify that running_under_virtualenv was called
                                    mock_venv.assert_called_once()
                                    
                                    # Should proceed normally
                                    mock_sys_exit.assert_not_called()
                                    mock_logger.assert_not_called()
                                    assert result == 0


class TestRequireVirtualenvConditionLogic:
    """Test the specific conditional logic implementation."""
    
    def test_require_venv_false_bypasses_all_checks(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that require_venv=False bypasses all virtualenv checks."""
        # Setup: no virtualenv, require_venv=False (should bypass all checks)
        mock_virtualenv_detection(False)
        mock_options.require_venv = False
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'run', return_value=0):
            with patch.object(command, 'parse_args', return_value=(mock_options, [])):
                with patch('pip._internal.cli.base_command.setup_logging'):
                    with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                        with patch('pip._internal.cli.base_command.tempdir_registry'):
                            with patch('pip._internal.cli.base_command.reconfigure'):
                                with patch('pip._internal.cli.base_command.running_under_virtualenv') as mock_venv:
                                    
                                    result = command._main([])
                                    
                                    # Should not even check virtualenv detection
                                    mock_venv.assert_not_called()
                                    mock_sys_exit.assert_not_called()
                                    mock_logger.assert_not_called()
                                    assert result == 0
    
    def test_ignore_require_venv_bypasses_venv_check(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that ignore_require_venv=True bypasses virtualenv checks."""
        # Setup: no virtualenv, require_venv=True, ignore_require_venv=True
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=True)
        
        with patch.object(command, 'run', return_value=0):
            with patch.object(command, 'parse_args', return_value=(mock_options, [])):
                with patch('pip._internal.cli.base_command.setup_logging'):
                    with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                        with patch('pip._internal.cli.base_command.tempdir_registry'):
                            with patch('pip._internal.cli.base_command.reconfigure'):
                                with patch('pip._internal.cli.base_command.running_under_virtualenv') as mock_venv:
                                    
                                    result = command._main([])
                                    
                                    # Should not check virtualenv detection due to ignore flag
                                    mock_venv.assert_not_called()
                                    mock_sys_exit.assert_not_called()
                                    mock_logger.assert_not_called()
                                    assert result == 0
    
    def test_both_conditions_true_triggers_venv_check(
        self, 
        mock_options: Mock,
        mock_virtualenv_detection,
        mock_sys_exit: Mock,
        mock_logger: Mock
    ):
        """Test that both require_venv=True and ignore_require_venv=False triggers the check."""
        # Setup: no virtualenv, require_venv=True, ignore_require_venv=False
        mock_virtualenv_detection(False)
        mock_options.require_venv = True
        
        command = TestCommand(ignore_require_venv=False)
        
        with patch.object(command, 'parse_args', return_value=(mock_options, [])):
            with patch('pip._internal.cli.base_command.setup_logging'):
                with patch('pip._internal.cli.base_command.global_tempdir_manager'):
                    with patch('pip._internal.cli.base_command.tempdir_registry'):
                        with patch('pip._internal.cli.base_command.reconfigure'):
                            with patch('pip._internal.cli.base_command.running_under_virtualenv') as mock_venv:
                                
                                mock_venv.return_value = False
                                
                                command._main([])
                                
                                # Should check virtualenv detection and exit with error
                                mock_venv.assert_called_once()
                                mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
                                mock_logger.assert_called_once_with(
                                    "Could not find an activated virtualenv (required)."
                                )