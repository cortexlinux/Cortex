#!/usr/bin/env python3
"""
Tests for System Requirements Checker module.
"""

import pytest
import json
import platform
from unittest.mock import Mock, patch, MagicMock, mock_open
from requirements_checker import (
    SystemRequirementsChecker, PackageRequirements,
    RequirementCheck, CheckStatus, Severity,
    check_requirements
)


class TestRequirementCheck:
    """Test RequirementCheck dataclass."""
    
    def test_check_creation(self):
        """Test creating a requirement check."""
        check = RequirementCheck(
            name="Test Check",
            status=CheckStatus.PASS,
            message="Everything OK"
        )
        assert check.name == "Test Check"
        assert check.status == CheckStatus.PASS
        assert check.can_continue is True
    
    def test_check_string_representation(self):
        """Test string formatting of checks."""
        check = RequirementCheck(
            name="Disk Space",
            status=CheckStatus.PASS,
            message="100GB available"
        )
        str_repr = str(check)
        assert "✅" in str_repr
        assert "Disk Space" in str_repr
        assert "100GB available" in str_repr
    
    def test_check_severity_levels(self):
        """Test different severity levels."""
        info_check = RequirementCheck(
            name="Info", status=CheckStatus.INFO,
            message="Info", severity=Severity.INFO
        )
        assert info_check.severity == Severity.INFO
        
        warning_check = RequirementCheck(
            name="Warning", status=CheckStatus.WARNING,
            message="Warning", severity=Severity.WARNING
        )
        assert warning_check.severity == Severity.WARNING
        
        error_check = RequirementCheck(
            name="Error", status=CheckStatus.ERROR,
            message="Error", severity=Severity.ERROR
        )
        assert error_check.severity == Severity.ERROR


class TestPackageRequirements:
    """Test PackageRequirements dataclass."""
    
    def test_requirements_creation(self):
        """Test creating package requirements."""
        req = PackageRequirements(
            package_name="test-package",
            min_disk_space_gb=10.0,
            min_ram_gb=4.0
        )
        assert req.package_name == "test-package"
        assert req.min_disk_space_gb == 10.0
        assert req.min_ram_gb == 4.0
    
    def test_requirements_to_dict(self):
        """Test converting requirements to dictionary."""
        req = PackageRequirements(
            package_name="test",
            required_packages=['gcc', 'make']
        )
        data = req.to_dict()
        assert data['package_name'] == "test"
        assert 'gcc' in data['required_packages']


class TestSystemRequirementsChecker:
    """Test SystemRequirementsChecker class."""
    
    def test_checker_creation(self):
        """Test creating a requirements checker."""
        checker = SystemRequirementsChecker()
        assert checker.disk_buffer_percent == 20.0
        assert checker.enable_interactive is True
        assert checker.force_mode is False
        assert len(checker.checks) == 0
    
    def test_force_mode(self):
        """Test force mode bypasses checks."""
        checker = SystemRequirementsChecker(force_mode=True)
        assert checker.force_mode is True
        assert checker.can_proceed() is True  # Always true in force mode
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_disk_space_pass(self, mock_psutil):
        """Test disk space check passes with sufficient space."""
        # Mock 100GB free
        mock_disk = Mock()
        mock_disk.free = 100 * 1024 ** 3
        mock_psutil.disk_usage.return_value = mock_disk
        
        checker = SystemRequirementsChecker()
        result = checker.check_disk_space(required_gb=50.0)
        
        assert result.status == CheckStatus.PASS
        assert "100.0GB" in result.message
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_disk_space_warning(self, mock_psutil):
        """Test disk space check warning with low buffer."""
        # Mock 55GB free (enough for 50GB but less than 60GB with 20% buffer)
        mock_disk = Mock()
        mock_disk.free = 55 * 1024 ** 3
        mock_psutil.disk_usage.return_value = mock_disk
        
        checker = SystemRequirementsChecker(disk_buffer_percent=20.0)
        result = checker.check_disk_space(required_gb=50.0)
        
        assert result.status == CheckStatus.WARNING
        assert result.can_continue is True
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_disk_space_error(self, mock_psutil):
        """Test disk space check error with insufficient space."""
        # Mock 10GB free
        mock_disk = Mock()
        mock_disk.free = 10 * 1024 ** 3
        mock_psutil.disk_usage.return_value = mock_disk
        
        checker = SystemRequirementsChecker()
        result = checker.check_disk_space(required_gb=50.0)
        
        assert result.status == CheckStatus.ERROR
        assert result.can_continue is False
        assert result.suggestion is not None
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_ram_pass(self, mock_psutil):
        """Test RAM check passes with sufficient memory."""
        # Mock 16GB total, 8GB available
        mock_mem = Mock()
        mock_mem.total = 16 * 1024 ** 3
        mock_mem.available = 8 * 1024 ** 3
        mock_psutil.virtual_memory.return_value = mock_mem
        
        checker = SystemRequirementsChecker()
        result = checker.check_ram(required_gb=8.0, required_available_gb=4.0)
        
        assert result.status == CheckStatus.PASS
        assert "16.0GB" in result.message
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_ram_insufficient_total(self, mock_psutil):
        """Test RAM check error with insufficient total RAM."""
        # Mock 4GB total
        mock_mem = Mock()
        mock_mem.total = 4 * 1024 ** 3
        mock_mem.available = 3 * 1024 ** 3
        mock_psutil.virtual_memory.return_value = mock_mem
        
        checker = SystemRequirementsChecker()
        result = checker.check_ram(required_gb=8.0)
        
        assert result.status == CheckStatus.ERROR
        assert result.can_continue is False
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_ram_low_available(self, mock_psutil):
        """Test RAM check warning with low available memory."""
        # Mock 16GB total, 0.5GB available
        mock_mem = Mock()
        mock_mem.total = 16 * 1024 ** 3
        mock_mem.available = 0.5 * 1024 ** 3
        mock_psutil.virtual_memory.return_value = mock_mem
        
        checker = SystemRequirementsChecker()
        result = checker.check_ram(required_gb=8.0, required_available_gb=2.0)
        
        assert result.status == CheckStatus.WARNING
        assert result.can_continue is True
        assert "Close other applications" in result.suggestion
    
    def test_check_architecture_supported(self):
        """Test architecture check with supported architecture."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.machine', return_value='x86_64'):
            result = checker.check_architecture(['x86_64', 'amd64'])
            assert result.status == CheckStatus.PASS
    
    def test_check_architecture_unsupported(self):
        """Test architecture check with unsupported architecture."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.machine', return_value='armv7l'):
            result = checker.check_architecture(['x86_64'])
            assert result.status == CheckStatus.ERROR
            assert result.can_continue is False
    
    def test_check_architecture_normalization(self):
        """Test that architectures are normalized correctly."""
        checker = SystemRequirementsChecker()
        
        # amd64 should map to x86_64
        with patch('platform.machine', return_value='amd64'):
            result = checker.check_architecture(['x86_64'])
            assert result.status == CheckStatus.PASS
    
    @patch('builtins.open', mock_open(read_data='NAME="Ubuntu"\nVERSION_ID="22.04"'))
    @patch('os.path.exists', return_value=True)
    def test_detect_linux_distribution(self, mock_exists):
        """Test Linux distribution detection."""
        checker = SystemRequirementsChecker()
        name, version = checker._detect_linux_distribution()
        
        assert name == "Ubuntu"
        assert version == "22.04"
    
    def test_check_os_compatibility_pass(self):
        """Test OS compatibility check passes."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.system', return_value='Linux'):
            with patch.object(checker, '_detect_linux_distribution', return_value=('Ubuntu', '22.04')):
                result = checker.check_os_compatibility(['ubuntu', 'debian'])
                assert result.status == CheckStatus.PASS
    
    def test_check_os_compatibility_warning(self):
        """Test OS compatibility warning for unsupported OS."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.system', return_value='Linux'):
            with patch.object(checker, '_detect_linux_distribution', return_value=('Gentoo', '2.14')):
                result = checker.check_os_compatibility(['ubuntu'])
                assert result.status == CheckStatus.WARNING
                assert result.can_continue is True
    
    @patch('shutil.which', return_value='/usr/bin/gcc')
    def test_is_package_installed_true(self, mock_which):
        """Test package detection when installed."""
        checker = SystemRequirementsChecker()
        assert checker._is_package_installed('gcc') is True
    
    @patch('shutil.which', return_value=None)
    def test_is_package_installed_false(self, mock_which):
        """Test package detection when not installed."""
        checker = SystemRequirementsChecker()
        assert checker._is_package_installed('gcc') is False
    
    @patch('shutil.which', side_effect=lambda x: '/usr/bin/' + x if x in ['gcc', 'make'] else None)
    def test_check_prerequisites_all_installed(self, mock_which):
        """Test prerequisite check when all packages installed."""
        checker = SystemRequirementsChecker()
        results = checker.check_prerequisites(['gcc', 'make'])
        
        assert len(results) == 2
        assert all(r.status == CheckStatus.PASS for r in results)
    
    @patch('shutil.which', return_value=None)
    def test_check_prerequisites_missing(self, mock_which):
        """Test prerequisite check when packages missing."""
        checker = SystemRequirementsChecker()
        results = checker.check_prerequisites(['gcc', 'make'])
        
        assert len(results) == 2
        assert all(r.status == CheckStatus.ERROR for r in results)
        assert all(not r.can_continue for r in results)
    
    @patch('shutil.which')
    def test_check_prerequisites_optional(self, mock_which):
        """Test optional package checking."""
        mock_which.return_value = None
        
        checker = SystemRequirementsChecker()
        results = checker.check_prerequisites([], optional_packages=['cuda'])
        
        assert len(results) == 1
        assert results[0].status == CheckStatus.WARNING
        assert results[0].can_continue is True
    
    def test_get_install_command_apt(self):
        """Test install command generation for apt."""
        checker = SystemRequirementsChecker()
        
        with patch('os.path.exists', side_effect=lambda p: p == '/usr/bin/apt'):
            cmd = checker._get_install_command('gcc')
            assert 'apt-get install gcc' in cmd
    
    @patch('shutil.which', side_effect=lambda x: '/usr/bin/nvidia-smi' if x == 'nvidia-smi' else None)
    @patch('subprocess.run')
    def test_check_gpu_nvidia_detected(self, mock_run, mock_which):
        """Test GPU check detects NVIDIA GPU."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "NVIDIA GeForce RTX 3090, 24576 MiB"
        mock_run.return_value = mock_result
        
        checker = SystemRequirementsChecker()
        result = checker.check_gpu(requires_gpu=False)
        
        assert result.status == CheckStatus.PASS
        assert "NVIDIA" in result.message
    
    @patch('shutil.which', return_value=None)
    def test_check_gpu_not_detected_warning(self, mock_which):
        """Test GPU check warns when no GPU detected (not required)."""
        checker = SystemRequirementsChecker()
        result = checker.check_gpu(requires_gpu=False)
        
        assert result.status == CheckStatus.WARNING
        assert result.can_continue is True
    
    @patch('shutil.which', return_value=None)
    def test_check_gpu_not_detected_error(self, mock_which):
        """Test GPU check errors when GPU required but not found."""
        checker = SystemRequirementsChecker()
        result = checker.check_gpu(requires_gpu=True)
        
        assert result.status == CheckStatus.ERROR
        assert result.can_continue is False
    
    def test_check_python_version_pass(self):
        """Test Python version check passes."""
        checker = SystemRequirementsChecker()
        result = checker.check_python_version(min_version=(3, 6))
        
        assert result.status == CheckStatus.PASS
    
    def test_check_python_version_fail(self):
        """Test Python version check fails with old version."""
        checker = SystemRequirementsChecker()
        # Require impossibly high version
        result = checker.check_python_version(min_version=(9, 9))
        
        assert result.status == CheckStatus.ERROR
        assert result.can_continue is False


class TestIntegration:
    """Integration tests."""
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    @patch('platform.system', return_value='Linux')
    @patch('platform.machine', return_value='x86_64')
    @patch('shutil.which', side_effect=lambda x: '/usr/bin/' + x if x in ['gcc', 'make'] else None)
    def test_check_all_requirements_pass(self, mock_which, mock_machine, mock_system, mock_psutil):
        """Test complete requirements check passing."""
        # Mock system resources
        mock_disk = Mock()
        mock_disk.free = 100 * 1024 ** 3
        mock_psutil.disk_usage.return_value = mock_disk
        
        mock_mem = Mock()
        mock_mem.total = 16 * 1024 ** 3
        mock_mem.available = 8 * 1024 ** 3
        mock_psutil.virtual_memory.return_value = mock_mem
        
        # Create checker and requirements
        checker = SystemRequirementsChecker()
        requirements = PackageRequirements(
            package_name="test-package",
            min_disk_space_gb=10.0,
            min_ram_gb=8.0,
            required_packages=['gcc', 'make']
        )
        
        with patch.object(checker, '_detect_linux_distribution', return_value=('Ubuntu', '22.04')):
            results = checker.check_all(requirements)
        
        # Should have disk, RAM, OS, arch, and 2 prerequisite checks
        assert len(results) >= 5
        assert not checker.has_errors
    
    @patch('requirements_checker.PSUTIL_AVAILABLE', True)
    @patch('requirements_checker.psutil')
    def test_check_all_with_errors(self, mock_psutil):
        """Test complete check with errors."""
        # Mock insufficient disk space
        mock_disk = Mock()
        mock_disk.free = 5 * 1024 ** 3  # Only 5GB
        mock_psutil.disk_usage.return_value = mock_disk
        
        # Mock sufficient RAM
        mock_mem = Mock()
        mock_mem.total = 16 * 1024 ** 3
        mock_mem.available = 8 * 1024 ** 3
        mock_psutil.virtual_memory.return_value = mock_mem
        
        checker = SystemRequirementsChecker()
        requirements = PackageRequirements(
            package_name="test",
            min_disk_space_gb=50.0  # Need 50GB
        )
        
        results = checker.check_all(requirements)
        
        assert checker.has_errors
        assert not checker.can_proceed()
    
    def test_display_json_output(self, capsys):
        """Test JSON output mode."""
        checker = SystemRequirementsChecker(json_output=True)
        checker.checks = [
            RequirementCheck(
                name="Test", status=CheckStatus.PASS,
                message="OK", actual_value="100GB"
            )
        ]
        
        checker.display_results()
        
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        assert 'checks' in data
        assert len(data['checks']) == 1
        assert data['checks'][0]['name'] == "Test"
    
    @patch('builtins.input', return_value='y')
    def test_prompt_continue_yes(self, mock_input):
        """Test user chooses to continue."""
        checker = SystemRequirementsChecker()
        checker.has_warnings = True
        
        result = checker.prompt_continue()
        assert result is True
    
    @patch('builtins.input', return_value='n')
    def test_prompt_continue_no(self, mock_input):
        """Test user chooses not to continue."""
        checker = SystemRequirementsChecker()
        checker.has_warnings = True
        
        result = checker.prompt_continue()
        assert result is False
    
    def test_prompt_skipped_when_no_warnings(self):
        """Test prompt skipped when no warnings."""
        checker = SystemRequirementsChecker()
        checker.has_warnings = False
        
        result = checker.prompt_continue()
        assert result is True
    
    def test_prompt_skipped_in_force_mode(self):
        """Test prompt skipped in force mode."""
        checker = SystemRequirementsChecker(force_mode=True)
        checker.has_warnings = True
        
        result = checker.prompt_continue()
        assert result is True


class TestPackageDatabase:
    """Test package requirements database."""
    
    def test_oracle_requirements_exist(self):
        """Test oracle-23-ai requirements are defined."""
        assert 'oracle-23-ai' in SystemRequirementsChecker.PACKAGE_REQUIREMENTS
        
        oracle_req = SystemRequirementsChecker.PACKAGE_REQUIREMENTS['oracle-23-ai']
        assert oracle_req.min_disk_space_gb == 30.0
        assert oracle_req.min_ram_gb == 8.0
        assert 'gcc' in oracle_req.required_packages
    
    def test_postgresql_requirements_exist(self):
        """Test postgresql requirements are defined."""
        assert 'postgresql' in SystemRequirementsChecker.PACKAGE_REQUIREMENTS
        
        pg_req = SystemRequirementsChecker.PACKAGE_REQUIREMENTS['postgresql']
        assert pg_req.min_disk_space_gb == 2.0
        assert pg_req.min_ram_gb == 2.0
    
    def test_docker_requirements_exist(self):
        """Test docker requirements are defined."""
        assert 'docker' in SystemRequirementsChecker.PACKAGE_REQUIREMENTS
        
        docker_req = SystemRequirementsChecker.PACKAGE_REQUIREMENTS['docker']
        assert docker_req.min_disk_space_gb == 10.0
        assert 'curl' in docker_req.required_packages


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_check_with_exception_handling(self):
        """Test that exceptions are handled gracefully."""
        checker = SystemRequirementsChecker()
        
        with patch('requirements_checker.PSUTIL_AVAILABLE', False):
            with patch('os.name', 'posix'):
                with patch('subprocess.run', side_effect=Exception("Test error")):
                    result = checker.check_disk_space(10.0)
                    # Should return warning, not crash
                    assert result.status == CheckStatus.WARNING
                    assert result.can_continue is True
    
    def test_empty_requirements(self):
        """Test checking with minimal requirements."""
        checker = SystemRequirementsChecker()
        requirements = PackageRequirements(package_name="minimal")
        
        results = checker.check_all(requirements)
        
        # Should at least check disk, RAM, OS, arch
        assert len(results) >= 4
    
    @patch('requirements_checker.RICH_AVAILABLE', False)
    def test_display_without_rich(self, capsys):
        """Test display works without rich library."""
        checker = SystemRequirementsChecker()
        checker.checks = [
            RequirementCheck(
                name="Test",
                status=CheckStatus.PASS,
                message="OK"
            )
        ]
        
        checker.display_results()
        
        captured = capsys.readouterr()
        assert "Checking system requirements" in captured.out
        assert "Test" in captured.out
    
    def test_os_detection_windows(self):
        """Test OS detection on Windows."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.system', return_value='Windows'):
            with patch('platform.version', return_value='10.0.19045'):
                result = checker.check_os_compatibility()
                assert result.status == CheckStatus.INFO
                assert "Windows" in result.message
    
    def test_os_detection_macos(self):
        """Test OS detection on macOS."""
        checker = SystemRequirementsChecker()
        
        with patch('platform.system', return_value='Darwin'):
            with patch('platform.mac_ver', return_value=('13.5', ('', '', ''), '')):
                result = checker.check_os_compatibility()
                assert result.status == CheckStatus.INFO
                assert "macOS" in result.message


class TestCLI:
    """Test CLI functionality."""
    
    @patch('requirements_checker.check_requirements', return_value=True)
    def test_main_function(self, mock_check):
        """Test main CLI function."""
        with patch('sys.argv', ['prog', 'postgresql']):
            from requirements_checker import main
            
            with pytest.raises(SystemExit) as exc:
                main()
            
            assert exc.value.code == 0
            mock_check.assert_called_once()
    
    @patch('requirements_checker.check_requirements', return_value=False)
    def test_main_function_failure(self, mock_check):
        """Test main CLI exits with error on failure."""
        with patch('sys.argv', ['prog', 'unknown-package']):
            from requirements_checker import main
            
            with pytest.raises(SystemExit) as exc:
                main()
            
            assert exc.value.code == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

