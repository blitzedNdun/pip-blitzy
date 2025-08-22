"""Functional tests for the --require-virtualenv CLI flag."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from pip._internal.cli.status_codes import VIRTUALENV_NOT_FOUND
from tests.lib import PipTestEnvironment
from tests.lib.venv import VirtualEnvironment


class TestRequireVirtualenvFunctional:
    """Functional tests for --require-virtualenv enforcement logic.
    
    Tests the 8 truth matrix scenarios of has_venv, require_venv, and ignore_require_venv
    to ensure proper enforcement of virtual environment requirements across pip commands.
    """
    
    class TestWithVirtualenv:
        """Tests when running inside a virtual environment."""
        
        def test_require_venv_true_ignore_false_in_virtualenv(self, script: PipTestEnvironment, tmpdir) -> None:
            """Test --require-virtualenv with commands that enforce it, inside virtualenv.
            
            Truth matrix case: has_venv=True, require_venv=True, ignore_require_venv=False
            Expected: Command executes successfully
            """
            # Create a virtual environment
            venv = VirtualEnvironment(tmpdir.join("test_venv"))
            venv.create()
            
            # Run pip install with --require-virtualenv inside the virtualenv
            result = venv.pip("install", "--require-virtualenv", "wheel")
            
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
            # Verify the package was actually installed in the virtualenv
            installed_packages = venv.pip("list", "--format=json")
            packages = json.loads(installed_packages.stdout)
            package_names = [pkg["name"].lower() for pkg in packages]
            assert "wheel" in package_names
        
        def test_require_venv_true_ignore_true_in_virtualenv(self, tmpdir) -> None:
            """Test --require-virtualenv with commands that ignore it, inside virtualenv.
            
            Truth matrix case: has_venv=True, require_venv=True, ignore_require_venv=True
            Expected: Command executes successfully (bypass requirement)
            """
            # Create a virtual environment
            venv = VirtualEnvironment(tmpdir.join("test_venv"))
            venv.create()
            
            # Use 'pip help' which has ignore_require_venv=True
            result = venv.pip("help", "--require-virtualenv")
            
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
            assert "Usage:" in result.stdout  # Help command should work
        
        def test_require_venv_false_ignore_false_in_virtualenv(self, script: PipTestEnvironment, tmpdir) -> None:
            """Test without --require-virtualenv with commands that enforce it, inside virtualenv.
            
            Truth matrix case: has_venv=True, require_venv=False, ignore_require_venv=False
            Expected: Command executes successfully
            """
            # Create a virtual environment
            venv = VirtualEnvironment(tmpdir.join("test_venv"))
            venv.create()
            
            # Run pip install without --require-virtualenv inside the virtualenv
            result = venv.pip("install", "wheel")
            
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        def test_require_venv_false_ignore_true_in_virtualenv(self, tmpdir) -> None:
            """Test without --require-virtualenv with commands that ignore it, inside virtualenv.
            
            Truth matrix case: has_venv=True, require_venv=False, ignore_require_venv=True
            Expected: Command executes successfully
            """
            # Create a virtual environment
            venv = VirtualEnvironment(tmpdir.join("test_venv"))
            venv.create()
            
            # Use 'pip help' without --require-virtualenv
            result = venv.pip("help")
            
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
            assert "Usage:" in result.stdout  # Help command should work
    
    class TestWithoutVirtualenv:
        """Tests when NOT running in a virtual environment."""
        
        def test_require_venv_true_ignore_false_outside_virtualenv(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with commands that enforce it, outside virtualenv.
            
            Truth matrix case: has_venv=False, require_venv=True, ignore_require_venv=False
            Expected: Exit with code 3 (VIRTUALENV_NOT_FOUND)
            """
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Run pip install with --require-virtualenv outside any virtualenv
                result = script.pip("install", "--require-virtualenv", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_venv_true_ignore_true_outside_virtualenv(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with commands that ignore it, outside virtualenv.
            
            Truth matrix case: has_venv=False, require_venv=True, ignore_require_venv=True
            Expected: Command executes successfully (bypass requirement)
            """
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Use 'pip help' which has ignore_require_venv=True
                result = script.pip("help", "--require-virtualenv")
                
                assert result.returncode == 0
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                assert "Usage:" in result.stdout  # Help command should work
        
        def test_require_venv_false_ignore_false_outside_virtualenv(self, script: PipTestEnvironment) -> None:
            """Test without --require-virtualenv with commands that enforce it, outside virtualenv.
            
            Truth matrix case: has_venv=False, require_venv=False, ignore_require_venv=False
            Expected: Command executes successfully
            """
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Run pip install without --require-virtualenv outside virtualenv
                result = script.pip("install", "wheel")
                
                assert result.returncode == 0
                assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        def test_require_venv_false_ignore_true_outside_virtualenv(self, script: PipTestEnvironment) -> None:
            """Test without --require-virtualenv with commands that ignore it, outside virtualenv.
            
            Truth matrix case: has_venv=False, require_venv=False, ignore_require_venv=True
            Expected: Command executes successfully
            """
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Use 'pip help' without --require-virtualenv
                result = script.pip("help")
                
                assert result.returncode == 0
                assert "Could not find an activated virtualenv (required)." not in result.stderr
                assert "Usage:" in result.stdout  # Help command should work
    
    class TestCommandSpecificBehavior:
        """Tests for command-specific ignore_require_venv behavior."""
        
        def test_commands_that_ignore_require_venv(self, script: PipTestEnvironment) -> None:
            """Test commands with ignore_require_venv=True bypass the check.
            
            These commands should never enforce --require-virtualenv regardless of the flag.
            """
            # Mock running_under_virtualenv to return False to test bypass
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Commands that have ignore_require_venv=True
                ignore_commands = [
                    ["help", "--require-virtualenv"],
                    ["completion", "--require-virtualenv", "bash"],
                    ["debug", "--require-virtualenv"],
                ]
                
                for cmd_args in ignore_commands:
                    result = script.pip(*cmd_args)
                    
                    # All these commands should succeed despite --require-virtualenv + no venv
                    assert result.returncode == 0, f"Command {' '.join(cmd_args)} failed"
                    assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        def test_commands_that_enforce_require_venv(self, script: PipTestEnvironment) -> None:
            """Test commands with ignore_require_venv=False enforce the check.
            
            These commands should enforce --require-virtualenv when flag is set.
            """
            # Mock running_under_virtualenv to return False to test enforcement
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Commands that have ignore_require_venv=False (default behavior)
                enforce_commands = [
                    ["install", "--require-virtualenv", "wheel"],
                    ["uninstall", "--require-virtualenv", "-y", "wheel"],  # -y to skip confirmation
                    ["download", "--require-virtualenv", "wheel"],
                    ["list", "--require-virtualenv"],
                    ["show", "--require-virtualenv", "wheel"],
                    ["freeze", "--require-virtualenv"],
                    ["check", "--require-virtualenv"],
                ]
                
                for cmd_args in enforce_commands:
                    result = script.pip(*cmd_args, expect_error=True)
                    
                    # All these commands should fail with VIRTUALENV_NOT_FOUND
                    assert result.returncode == VIRTUALENV_NOT_FOUND, f"Command {' '.join(cmd_args)} didn't exit with code 3"
                    assert "Could not find an activated virtualenv (required)." in result.stderr
    
    class TestErrorMessageAndExitCode:
        """Tests for proper error message and exit code validation."""
        
        def test_error_message_exact_text(self, script: PipTestEnvironment) -> None:
            """Test that the exact error message appears when virtualenv is required but missing."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_exit_code_is_three(self, script: PipTestEnvironment) -> None:
            """Test that exit code is exactly 3 (VIRTUALENV_NOT_FOUND) when virtualenv required but missing."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "wheel", expect_error=True)
                
                assert result.returncode == 3  # VIRTUALENV_NOT_FOUND constant value
                assert result.returncode == VIRTUALENV_NOT_FOUND  # Verify constant matches
    
    class TestRealVirtualenvDetection:
        """Tests using real virtual environment detection without mocking."""
        
        def test_real_virtualenv_creation_and_detection(self, tmpdir) -> None:
            """Test that real virtualenv creation and detection works end-to-end."""
            # Create a real virtual environment using VirtualEnvironment helper
            venv_path = tmpdir.join("real_test_venv")
            venv = VirtualEnvironment(venv_path)
            venv.create()
            
            # Test that the virtualenv detection works inside the real virtualenv
            result = venv.pip("install", "--require-virtualenv", "--dry-run", "wheel")
            
            # Should succeed because we're actually in a virtualenv
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        @pytest.mark.parametrize("venv_type", ["venv", "virtualenv"])
        def test_different_virtualenv_types(self, tmpdir, venv_type: str) -> None:
            """Test --require-virtualenv works with different virtualenv creation methods.
            
            Tests both PEP 405 venv and legacy virtualenv packages.
            """
            # Skip virtualenv test if not available
            if venv_type == "virtualenv":
                pytest.importorskip("virtualenv")
            
            venv_path = tmpdir.join(f"{venv_type}_test")
            
            # Create virtualenv using the specified method
            if venv_type == "venv":
                # Use built-in venv module (PEP 405)
                subprocess.run([
                    sys.executable, "-m", "venv", str(venv_path)
                ], check=True)
            else:
                # Use virtualenv package 
                subprocess.run([
                    sys.executable, "-m", "virtualenv", str(venv_path)
                ], check=True)
            
            # Create VirtualEnvironment wrapper for the created environment
            venv = VirtualEnvironment(venv_path)
            
            # Test --require-virtualenv works with this type of environment
            result = venv.pip("install", "--require-virtualenv", "--dry-run", "wheel")
            
            assert result.returncode == 0
            assert "Could not find an activated virtualenv (required)." not in result.stderr
        
        def test_system_python_detection_without_virtualenv(self, script: PipTestEnvironment) -> None:
            """Test that running with system Python properly detects no virtualenv.
            
            This test runs without mocking to ensure real-world behavior.
            """
            # Create a subprocess that runs outside any virtualenv
            # We'll create a separate Python process to ensure clean environment
            test_script = '''
import sys
import subprocess
import os

# Remove any virtualenv-related environment variables
env = os.environ.copy()
for key in list(env.keys()):
    if "VIRTUAL" in key or "CONDA" in key:
        del env[key]

# Reset sys.prefix and sys.base_prefix to ensure we're not in a virtualenv
# by running a completely separate Python process
result = subprocess.run([
    sys.executable, "-m", "pip", "install", "--require-virtualenv", "--dry-run", "wheel"
], env=env, capture_output=True, text=True)

print(f"Return code: {result.returncode}")
print(f"Stderr: {result.stderr}")
'''
            
            # Write the test script to a temporary file
            test_file = script.scratch_path / "test_no_venv.py"
            test_file.write_text(test_script)
            
            # Run the test script
            result = script.run("python", str(test_file))
            
            # The subprocess should exit with VIRTUALENV_NOT_FOUND
            # Note: We check the output since we're testing a subprocess
            assert "Return code: 3" in result.stdout
            assert "Could not find an activated virtualenv (required)." in result.stdout
    
    class TestEdgeCases:
        """Tests for edge cases and special scenarios."""
        
        def test_require_virtualenv_with_multiple_commands(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv behavior with multiple package operations."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Test installing multiple packages with --require-virtualenv
                result = script.pip("install", "--require-virtualenv", "wheel", "setuptools", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_requirements_file(self, script: PipTestEnvironment, tmpdir) -> None:
            """Test --require-virtualenv with requirements file installation."""
            # Create a requirements file
            req_file = tmpdir.join("requirements.txt")
            req_file.write("wheel>=0.30.0\nsetuptools>=40.0.0\n")
            
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "-r", str(req_file), expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_editable_install(self, script: PipTestEnvironment, tmpdir) -> None:
            """Test --require-virtualenv with editable installations."""
            # Create a simple package for editable install
            pkg_dir = tmpdir.join("test_package")
            pkg_dir.mkdir()
            pkg_dir.join("setup.py").write("""
from setuptools import setup
setup(name='test-package', version='1.0.0', py_modules=['test_package'])
""")
            pkg_dir.join("test_package.py").write("# Test package")
            
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "-e", str(pkg_dir), expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_upgrade_flag(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with --upgrade flag."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "--upgrade", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_order_independence(self, script: PipTestEnvironment) -> None:
            """Test that --require-virtualenv works regardless of argument position."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                # Test --require-virtualenv at different positions
                positions = [
                    ["install", "--require-virtualenv", "wheel"],
                    ["install", "wheel", "--require-virtualenv"],
                    ["--require-virtualenv", "install", "wheel"],
                ]
                
                for cmd_args in positions:
                    result = script.pip(*cmd_args, expect_error=True)
                    
                    assert result.returncode == VIRTUALENV_NOT_FOUND, f"Failed for args: {cmd_args}"
                    assert "Could not find an activated virtualenv (required)." in result.stderr
    
    class TestIntegrationWithExistingFlags:
        """Tests for integration with other pip flags and options."""
        
        def test_require_virtualenv_with_verbose_flag(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with --verbose flag."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "--verbose", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_quiet_flag(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with --quiet flag."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "--quiet", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                # Error message should still appear even with --quiet
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_no_deps_flag(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with --no-deps flag."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "--no-deps", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
        
        def test_require_virtualenv_with_force_reinstall(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with --force-reinstall flag."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result = script.pip("install", "--require-virtualenv", "--force-reinstall", "wheel", expect_error=True)
                
                assert result.returncode == VIRTUALENV_NOT_FOUND
                assert "Could not find an activated virtualenv (required)." in result.stderr
    
    class TestPerformanceAndCoverage:
        """Tests focused on performance and code coverage requirements."""
        
        def test_require_virtualenv_coverage_execution_paths(self, script: PipTestEnvironment, tmpdir) -> None:
            """Test all execution paths for comprehensive code coverage."""
            # Test path 1: Inside virtualenv with --require-virtualenv (should succeed)
            venv = VirtualEnvironment(tmpdir.join("coverage_venv"))
            venv.create()
            
            result1 = venv.pip("install", "--require-virtualenv", "--dry-run", "wheel")
            assert result1.returncode == 0
            
            # Test path 2: Outside virtualenv with --require-virtualenv (should fail)
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result2 = script.pip("install", "--require-virtualenv", "wheel", expect_error=True)
                assert result2.returncode == VIRTUALENV_NOT_FOUND
            
            # Test path 3: Outside virtualenv without --require-virtualenv (should succeed)
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result3 = script.pip("install", "--dry-run", "wheel")
                assert result3.returncode == 0
            
            # Test path 4: Command with ignore_require_venv=True (should always succeed)
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                result4 = script.pip("help", "--require-virtualenv")
                assert result4.returncode == 0
        
        def test_require_virtualenv_performance_timing(self, script: PipTestEnvironment) -> None:
            """Test that --require-virtualenv check doesn't significantly impact performance."""
            import time
            
            # Mock running_under_virtualenv to return True
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=True):
                # Time the execution with --require-virtualenv
                start_time = time.time()
                result1 = script.pip("install", "--require-virtualenv", "--dry-run", "wheel")
                with_flag_time = time.time() - start_time
                
                # Time the execution without --require-virtualenv  
                start_time = time.time()
                result2 = script.pip("install", "--dry-run", "wheel")
                without_flag_time = time.time() - start_time
                
                # Both should succeed
                assert result1.returncode == 0
                assert result2.returncode == 0
                
                # The virtualenv check should add minimal overhead (< 100ms difference)
                time_difference = abs(with_flag_time - without_flag_time)
                assert time_difference < 0.1, f"Virtualenv check added {time_difference:.3f}s overhead"
        
        def test_require_virtualenv_all_command_types(self, script: PipTestEnvironment) -> None:
            """Test --require-virtualenv with all major pip command types for coverage."""
            # Mock running_under_virtualenv to return False
            with mock.patch("pip._internal.utils.virtualenv.running_under_virtualenv", return_value=False):
                
                # Commands that should enforce (ignore_require_venv=False)
                enforce_commands = [
                    (["install", "--require-virtualenv", "--dry-run", "wheel"], True),
                    (["download", "--require-virtualenv", "--dest", str(script.scratch_path), "wheel"], True), 
                    (["list", "--require-virtualenv"], True),
                    (["show", "--require-virtualenv", "pip"], True),
                    (["freeze", "--require-virtualenv"], True),
                    (["check", "--require-virtualenv"], True),
                ]
                
                # Commands that should bypass (ignore_require_venv=True)  
                bypass_commands = [
                    (["help", "--require-virtualenv"], False),
                    (["debug", "--require-virtualenv"], False),
                    (["completion", "--require-virtualenv", "bash"], False),
                ]
                
                # Test enforcing commands
                for cmd_args, should_fail in enforce_commands:
                    if should_fail:
                        result = script.pip(*cmd_args, expect_error=True)
                        assert result.returncode == VIRTUALENV_NOT_FOUND, f"Command {cmd_args} should have failed"
                        assert "Could not find an activated virtualenv (required)." in result.stderr
                    else:
                        result = script.pip(*cmd_args)
                        assert result.returncode == 0, f"Command {cmd_args} should have succeeded"
                
                # Test bypassing commands
                for cmd_args, should_fail in bypass_commands:
                    result = script.pip(*cmd_args)
                    assert result.returncode == 0, f"Command {cmd_args} should bypass and succeed"
                    assert "Could not find an activated virtualenv (required)." not in result.stderr