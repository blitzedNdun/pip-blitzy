"""
Unit test module for the --require-virtualenv CLI flag

This module provides comprehensive testing for the virtual environment enforcement logic
in pip._internal.cli.base_command. Tests the 8 truth matrix scenarios for has_venv,
require_venv, and ignore_require_venv flags using mocked running_under_virtualenv()
function. Verifies SystemExit with VIRTUALENV_NOT_FOUND exit code when appropriate,
confirms commands with ignore_require_venv=True bypass the check, and ensures proper
error messages are logged.

Test Categories:
- Happy path: Virtual environment active, require_venv=True
- Error cases: No virtualenv, require_venv=True, ignore_require_venv=False  
- Edge cases: All truth matrix permutations
- Command variations: Testing both ignoring and non-ignoring commands

Test Data:
- Mock fixtures for controlling running_under_virtualenv() return value
- Command instances with ignore_require_venv=True/False
- Mocked sys.exit() calls for exit code validation

Coverage Requirements:
- Line coverage: ≥90% of base_command.py lines 219-223
- Branch coverage: Complete coverage of all conditional paths
- Function coverage: Complete coverage of virtualenv enforcement logic

Dependencies:
- pytest fixtures from tests/conftest.py
- unittest.mock for mocking virtualenv state and sys.exit
- Test command patterns from tests/unit/test_base_command.py
"""

from __future__ import annotations

import logging
import sys
from optparse import Values
from typing import NoReturn
from unittest.mock import Mock, patch

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import SUCCESS, VIRTUALENV_NOT_FOUND


class TestCommand(Command):
    """Test command class that does not ignore require_venv by default"""
    ignore_require_venv = False
    
    def __init__(self) -> None:
        super().__init__("test", "Test command for virtualenv enforcement")
    
    def run(self, options: Values, args: list[str]) -> int:
        """Simple run implementation that returns success"""
        return SUCCESS


class TestIgnoringCommand(Command):
    """Test command class that ignores require_venv (like cache, check, etc.)"""
    ignore_require_venv = True
    
    def __init__(self) -> None:
        super().__init__("test-ignore", "Test command that ignores virtualenv requirement")
    
    def run(self, options: Values, args: list[str]) -> int:
        """Simple run implementation that returns success"""
        return SUCCESS


@pytest.fixture
def mock_in_virtualenv():
    """Fixture to simulate being in a virtual environment"""
    with patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=True):
        yield


@pytest.fixture  
def mock_not_in_virtualenv():
    """Fixture to simulate not being in a virtual environment"""
    with patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
        yield


@pytest.fixture
def command_with_ignore_venv():
    """Returns a command instance with ignore_require_venv=True"""
    return TestIgnoringCommand()


@pytest.fixture
def command_without_ignore_venv():
    """Returns a command instance with ignore_require_venv=False"""
    return TestCommand()


@pytest.fixture
def mock_sys_exit():
    """Mock sys.exit to capture exit calls without actually exiting"""
    with patch("sys.exit") as mock_exit:
        yield mock_exit


class TestRequireVirtualenv:
    """Test --require-virtualenv enforcement logic"""
    
    class TestWithVirtualenv:
        """Tests when running inside a virtual environment"""
        
        def test_require_venv_true_ignore_false_has_venv_executes(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=True, ignore_require_venv=False, has_venv=True -> Command executes"""
            # Act
            result = command_without_ignore_venv.main(["--require-virtualenv"])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_true_ignore_true_has_venv_executes(
            self, mock_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=True, ignore_require_venv=True, has_venv=True -> Command executes"""
            # Act
            result = command_with_ignore_venv.main(["--require-virtualenv"])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_false_ignore_false_has_venv_executes(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=False, ignore_require_venv=False, has_venv=True -> Command executes"""
            # Act
            result = command_without_ignore_venv.main([])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_false_ignore_true_has_venv_executes(
            self, mock_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=False, ignore_require_venv=True, has_venv=True -> Command executes"""
            # Act
            result = command_with_ignore_venv.main([])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
    
    class TestWithoutVirtualenv:
        """Tests when NOT in a virtual environment"""
        
        def test_require_venv_true_ignore_false_no_venv_exits_with_error(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit, caplog
        ):
            """Test require_venv=True, ignore_require_venv=False, has_venv=False -> Exit with code 3"""
            # Arrange
            with caplog.at_level(logging.CRITICAL):
                # Act
                command_without_ignore_venv.main(["--require-virtualenv"])
            
            # Assert
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
        
        def test_require_venv_true_ignore_true_no_venv_executes(
            self, mock_not_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=True, ignore_require_venv=True, has_venv=False -> Command executes"""
            # Act
            result = command_with_ignore_venv.main(["--require-virtualenv"])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_false_ignore_false_no_venv_executes(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=False, ignore_require_venv=False, has_venv=False -> Command executes"""
            # Act
            result = command_without_ignore_venv.main([])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_false_ignore_true_no_venv_executes(
            self, mock_not_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Test require_venv=False, ignore_require_venv=True, has_venv=False -> Command executes"""
            # Act
            result = command_with_ignore_venv.main([])
            
            # Assert
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
    
    class TestCommandIgnoreFlag:
        """Tests for commands that ignore the requirement"""
        
        def test_cache_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test cache command bypasses virtualenv requirement"""
            from pip._internal.commands.cache import CacheCommand
            
            # Arrange
            command = CacheCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "dir"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_check_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test check command bypasses virtualenv requirement"""
            from pip._internal.commands.check import CheckCommand
            
            # Arrange
            command = CheckCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_completion_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test completion command bypasses virtualenv requirement"""
            from pip._internal.commands.completion import CompletionCommand
            
            # Arrange
            command = CompletionCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "--bash"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_configuration_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test configuration command bypasses virtualenv requirement"""
            from pip._internal.commands.configuration import ConfigurationCommand
            
            # Arrange
            command = ConfigurationCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "list"])
            
            # Assert - should not exit even without virtualenv  
            mock_sys_exit.assert_not_called()
        
        def test_debug_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test debug command bypasses virtualenv requirement"""
            from pip._internal.commands.debug import DebugCommand
            
            # Arrange
            command = DebugCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_freeze_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test freeze command bypasses virtualenv requirement"""
            from pip._internal.commands.freeze import FreezeCommand
            
            # Arrange  
            command = FreezeCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_hash_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test hash command bypasses virtualenv requirement"""
            from pip._internal.commands.hash import HashCommand
            
            # Arrange
            command = HashCommand()
            assert command.ignore_require_venv is True
            
            # Act - hash command needs a file argument
            with patch("builtins.open"):
                result = command.main(["--require-virtualenv", "dummy_file.txt"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_help_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test help command bypasses virtualenv requirement"""
            from pip._internal.commands.help import HelpCommand
            
            # Arrange
            command = HelpCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_index_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test index command bypasses virtualenv requirement"""
            from pip._internal.commands.index import IndexCommand
            
            # Arrange
            command = IndexCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "versions", "requests"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_inspect_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test inspect command bypasses virtualenv requirement"""
            from pip._internal.commands.inspect import InspectCommand
            
            # Arrange
            command = InspectCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "requests"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_list_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test list command bypasses virtualenv requirement"""
            from pip._internal.commands.list import ListCommand
            
            # Arrange
            command = ListCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_search_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test search command bypasses virtualenv requirement"""
            from pip._internal.commands.search import SearchCommand
            
            # Arrange
            command = SearchCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "requests"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
        
        def test_show_command_ignores_require_venv(self, mock_not_in_virtualenv, mock_sys_exit):
            """Test show command bypasses virtualenv requirement"""
            from pip._internal.commands.show import ShowCommand
            
            # Arrange
            command = ShowCommand()
            assert command.ignore_require_venv is True
            
            # Act
            result = command.main(["--require-virtualenv", "requests"])
            
            # Assert - should not exit even without virtualenv
            mock_sys_exit.assert_not_called()
    
    class TestEnforcingCommands:
        """Tests for commands that enforce the virtualenv requirement"""
        
        def test_install_command_enforces_require_venv(
            self, mock_not_in_virtualenv, mock_sys_exit, caplog
        ):
            """Test install command enforces virtualenv requirement"""
            from pip._internal.commands.install import InstallCommand
            
            # Arrange
            command = InstallCommand()
            assert command.ignore_require_venv is False
            
            with caplog.at_level(logging.CRITICAL):
                # Act
                command.main(["--require-virtualenv", "requests"])
            
            # Assert
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
        
        def test_uninstall_command_enforces_require_venv(
            self, mock_not_in_virtualenv, mock_sys_exit, caplog
        ):
            """Test uninstall command enforces virtualenv requirement"""
            from pip._internal.commands.uninstall import UninstallCommand
            
            # Arrange
            command = UninstallCommand()
            assert command.ignore_require_venv is False
            
            with caplog.at_level(logging.CRITICAL):
                # Act
                command.main(["--require-virtualenv", "requests"])
            
            # Assert
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
        
        def test_download_command_enforces_require_venv(
            self, mock_not_in_virtualenv, mock_sys_exit, caplog
        ):
            """Test download command enforces virtualenv requirement"""
            from pip._internal.commands.download import DownloadCommand
            
            # Arrange
            command = DownloadCommand()
            assert command.ignore_require_venv is False
            
            with caplog.at_level(logging.CRITICAL):
                # Act
                command.main(["--require-virtualenv", "requests"])
            
            # Assert
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
        
        def test_wheel_command_enforces_require_venv(
            self, mock_not_in_virtualenv, mock_sys_exit, caplog
        ):
            """Test wheel command enforces virtualenv requirement"""
            from pip._internal.commands.wheel import WheelCommand
            
            # Arrange
            command = WheelCommand()
            assert command.ignore_require_venv is False
            
            with caplog.at_level(logging.CRITICAL):
                # Act
                command.main(["--require-virtualenv", "requests"])
            
            # Assert
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
    
    class TestTruthMatrixScenarios:
        """Comprehensive truth matrix testing for all 8 combinations"""
        
        def test_scenario_1_has_venv_require_venv_ignore_venv(
            self, mock_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=True, require_venv=True, ignore_require_venv=True -> Execute"""
            result = command_with_ignore_venv.main(["--require-virtualenv"])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_2_has_venv_require_venv_no_ignore(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=True, require_venv=True, ignore_require_venv=False -> Execute"""
            result = command_without_ignore_venv.main(["--require-virtualenv"])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_3_has_venv_no_require_venv_ignore_venv(
            self, mock_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=True, require_venv=False, ignore_require_venv=True -> Execute"""
            result = command_with_ignore_venv.main([])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_4_has_venv_no_require_venv_no_ignore(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=True, require_venv=False, ignore_require_venv=False -> Execute"""
            result = command_without_ignore_venv.main([])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_5_no_venv_require_venv_ignore_venv(
            self, mock_not_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=False, require_venv=True, ignore_require_venv=True -> Execute"""
            result = command_with_ignore_venv.main(["--require-virtualenv"])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_6_no_venv_require_venv_no_ignore(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit, caplog
        ):
            """Truth matrix: has_venv=False, require_venv=True, ignore_require_venv=False -> Exit code 3"""
            with caplog.at_level(logging.CRITICAL):
                command_without_ignore_venv.main(["--require-virtualenv"])
            
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert "Could not find an activated virtualenv (required)." in caplog.text
        
        def test_scenario_7_no_venv_no_require_venv_ignore_venv(
            self, mock_not_in_virtualenv, command_with_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=False, require_venv=False, ignore_require_venv=True -> Execute"""
            result = command_with_ignore_venv.main([])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_scenario_8_no_venv_no_require_venv_no_ignore(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Truth matrix: has_venv=False, require_venv=False, ignore_require_venv=False -> Execute"""
            result = command_without_ignore_venv.main([])
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
    
    class TestVirtualenvDetectionMocking:
        """Test the mocking infrastructure for virtualenv detection"""
        
        def test_mock_in_virtualenv_fixture(self, mock_in_virtualenv):
            """Test that mock_in_virtualenv fixture correctly mocks True state"""
            from pip._internal.utils.virtualenv import running_under_virtualenv
            assert running_under_virtualenv() is True
        
        def test_mock_not_in_virtualenv_fixture(self, mock_not_in_virtualenv):
            """Test that mock_not_in_virtualenv fixture correctly mocks False state"""
            from pip._internal.utils.virtualenv import running_under_virtualenv
            assert running_under_virtualenv() is False
        
        def test_fixture_isolation(self):
            """Test that fixtures don't interfere with unmocked tests"""
            # This test runs without fixtures - should use real virtualenv detection
            from pip._internal.utils.virtualenv import running_under_virtualenv
            # Don't assert the actual value since it depends on test environment
            # Just verify the function is callable and returns a boolean
            result = running_under_virtualenv()
            assert isinstance(result, bool)
    
    class TestErrorHandlingAndLogging:
        """Test error handling and logging behavior"""
        
        def test_critical_log_message_exact_text(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit, caplog
        ):
            """Test exact error message is logged at CRITICAL level"""
            with caplog.at_level(logging.CRITICAL):
                command_without_ignore_venv.main(["--require-virtualenv"])
            
            # Verify exact message text
            assert "Could not find an activated virtualenv (required)." in caplog.text
            
            # Verify it's logged at CRITICAL level
            critical_records = [r for r in caplog.records if r.levelno == logging.CRITICAL]
            assert len(critical_records) == 1
            assert critical_records[0].message == "Could not find an activated virtualenv (required)."
        
        def test_exit_code_is_virtualenv_not_found(
            self, mock_not_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test that sys.exit is called with VIRTUALENV_NOT_FOUND status code"""
            command_without_ignore_venv.main(["--require-virtualenv"])
            
            # Verify exact exit code
            mock_sys_exit.assert_called_once_with(VIRTUALENV_NOT_FOUND)
            assert VIRTUALENV_NOT_FOUND == 3  # Verify the constant value
        
        def test_no_logging_when_virtualenv_available(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit, caplog
        ):
            """Test no error logging when virtualenv is available"""
            with caplog.at_level(logging.CRITICAL):
                result = command_without_ignore_venv.main(["--require-virtualenv"])
            
            # Should complete successfully without any critical logs
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
            
            critical_records = [r for r in caplog.records if r.levelno == logging.CRITICAL]
            assert len(critical_records) == 0
        
        def test_no_logging_when_ignoring_requirement(
            self, mock_not_in_virtualenv, command_with_ignore_venv, mock_sys_exit, caplog
        ):
            """Test no error logging when command ignores virtualenv requirement"""
            with caplog.at_level(logging.CRITICAL):
                result = command_with_ignore_venv.main(["--require-virtualenv"])
            
            # Should complete successfully without any critical logs
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
            
            critical_records = [r for r in caplog.records if r.levelno == logging.CRITICAL]
            assert len(critical_records) == 0
    
    class TestIntegrationWithExistingOptions:
        """Test integration with other CLI options"""
        
        def test_require_venv_with_other_flags(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test --require-virtualenv works with other common flags"""
            result = command_without_ignore_venv.main([
                "--require-virtualenv",
                "--verbose",
                "--no-cache-dir",
                "--disable-pip-version-check"
            ])
            
            assert result == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_flag_position_independence(
            self, mock_in_virtualenv, command_without_ignore_venv, mock_sys_exit
        ):
            """Test --require-virtualenv works regardless of flag position"""
            # Test flag at beginning
            result1 = command_without_ignore_venv.main([
                "--require-virtualenv", "--verbose"
            ])
            
            # Test flag at end  
            result2 = command_without_ignore_venv.main([
                "--verbose", "--require-virtualenv"
            ])
            
            assert result1 == SUCCESS
            assert result2 == SUCCESS
            mock_sys_exit.assert_not_called()
        
        def test_require_venv_flag_parsing_consistency(self, mock_in_virtualenv):
            """Test that require_venv option is parsed consistently"""
            # Test with our test command
            command = TestCommand()
            options, args = command.parse_args(["--require-virtualenv"])
            assert options.require_venv is True
            
            # Test without flag
            options, args = command.parse_args([])
            assert options.require_venv is False


class TestRealCommandImplementations:
    """Test actual pip command implementations to verify ignore_require_venv property"""
    
    def test_all_ignoring_commands_have_property_set(self):
        """Verify all commands that should ignore virtualenv have the property set"""
        ignoring_commands = [
            ("cache", "pip._internal.commands.cache", "CacheCommand"),
            ("check", "pip._internal.commands.check", "CheckCommand"), 
            ("completion", "pip._internal.commands.completion", "CompletionCommand"),
            ("config", "pip._internal.commands.configuration", "ConfigurationCommand"),
            ("debug", "pip._internal.commands.debug", "DebugCommand"),
            ("freeze", "pip._internal.commands.freeze", "FreezeCommand"),
            ("hash", "pip._internal.commands.hash", "HashCommand"),
            ("help", "pip._internal.commands.help", "HelpCommand"),
            ("index", "pip._internal.commands.index", "IndexCommand"),
            ("inspect", "pip._internal.commands.inspect", "InspectCommand"),
            ("list", "pip._internal.commands.list", "ListCommand"),
            ("search", "pip._internal.commands.search", "SearchCommand"),
            ("show", "pip._internal.commands.show", "ShowCommand"),
        ]
        
        for cmd_name, module_name, class_name in ignoring_commands:
            # Import the command class dynamically
            module = __import__(module_name, fromlist=[class_name])
            command_class = getattr(module, class_name)
            command_instance = command_class()
            
            # Verify the property is set correctly
            assert command_instance.ignore_require_venv is True, (
                f"{class_name} should have ignore_require_venv=True"
            )
    
    def test_all_enforcing_commands_have_default_property(self):
        """Verify commands that should enforce virtualenv use default False value"""
        enforcing_commands = [
            ("install", "pip._internal.commands.install", "InstallCommand"),
            ("uninstall", "pip._internal.commands.uninstall", "UninstallCommand"),
            ("download", "pip._internal.commands.download", "DownloadCommand"),
            ("wheel", "pip._internal.commands.wheel", "WheelCommand"),
        ]
        
        for cmd_name, module_name, class_name in enforcing_commands:
            # Import the command class dynamically
            module = __import__(module_name, fromlist=[class_name])
            command_class = getattr(module, class_name)
            command_instance = command_class()
            
            # Verify the property defaults to False (enforces requirement)
            assert command_instance.ignore_require_venv is False, (
                f"{class_name} should have ignore_require_venv=False (default)"
            )