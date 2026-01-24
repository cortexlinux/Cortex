import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.coordinator import (
    InstallationCoordinator,
    InstallationStep,
    StepStatus,
    example_cuda_install_plan,
    install_docker,
)

# Import the safe command execution utilities
from cortex.utils.commands import CommandResult, run_command


class TestInstallationStep(unittest.TestCase):
    def test_step_creation(self):
        step = InstallationStep(command="echo test", description="Test step")
        self.assertEqual(step.command, "echo test")
        self.assertEqual(step.description, "Test step")
        self.assertEqual(step.status, StepStatus.PENDING)

    def test_step_duration(self):
        step = InstallationStep(command="test", description="test")
        self.assertIsNone(step.duration())

        step.start_time = 100.0
        step.end_time = 105.5
        self.assertEqual(step.duration(), 5.5)


@patch("time.sleep")
class TestInstallationCoordinator(unittest.TestCase):
    def test_initialization(self, mock_sleep):
        commands = ["echo 1", "echo 2"]
        coordinator = InstallationCoordinator(commands)

        self.assertEqual(len(coordinator.steps), 2)
        self.assertEqual(coordinator.steps[0].command, "echo 1")
        self.assertEqual(coordinator.steps[1].command, "echo 2")

    def test_from_plan_initialization(self, mock_sleep):
        plan = [
            {"command": "echo 1", "description": "First step"},
            {"command": "echo 2", "rollback": "echo rollback"},
        ]

        coordinator = InstallationCoordinator.from_plan(plan)

        self.assertEqual(len(coordinator.steps), 2)
        self.assertEqual(coordinator.steps[0].description, "First step")
        self.assertEqual(coordinator.steps[1].description, "Step 2")
        self.assertTrue(coordinator.enable_rollback)
        self.assertEqual(coordinator.rollback_commands, ["echo rollback"])

    def test_initialization_with_descriptions(self, mock_sleep):
        commands = ["echo 1", "echo 2"]
        descriptions = ["First", "Second"]
        coordinator = InstallationCoordinator(commands, descriptions)

        self.assertEqual(coordinator.steps[0].description, "First")
        self.assertEqual(coordinator.steps[1].description, "Second")

    def test_initialization_mismatched_descriptions(self, mock_sleep):
        commands = ["echo 1", "echo 2"]
        descriptions = ["First"]

        with self.assertRaises(ValueError):
            InstallationCoordinator(commands, descriptions)

    @patch("cortex.coordinator.run_command")
    def test_execute_single_success(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=True, stdout="success", stderr="", return_code=0, command="echo test"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["echo test"])
        result = coordinator.execute()

        self.assertTrue(result.success)
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.steps[0].status, StepStatus.SUCCESS)

    @patch("cortex.coordinator.run_command")
    def test_execute_single_failure(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=False, stdout="", stderr="error", return_code=1, command="false"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["false"])
        result = coordinator.execute()

        self.assertFalse(result.success)
        self.assertEqual(result.failed_step, 0)
        self.assertEqual(result.steps[0].status, StepStatus.FAILED)

    @patch("cortex.coordinator.run_command")
    def test_execute_multiple_success(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=True, stdout="success", stderr="", return_code=0, command="echo test"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["echo 1", "echo 2", "echo 3"])
        result = coordinator.execute()

        self.assertTrue(result.success)
        self.assertEqual(len(result.steps), 3)
        self.assertTrue(all(s.status == StepStatus.SUCCESS for s in result.steps))

    @patch("cortex.coordinator.run_command")
    def test_execute_stop_on_error(self, mock_run_cmd, mock_sleep):
        def side_effect(cmd, *args, **kwargs):
            if "fail" in cmd:
                return CommandResult(success=False, stdout="", stderr="error", return_code=1, command=cmd)
            else:
                return CommandResult(success=True, stdout="success", stderr="", return_code=0, command=cmd)

        mock_run_cmd.side_effect = side_effect

        coordinator = InstallationCoordinator(["echo 1", "fail", "echo 3"], stop_on_error=True)
        result = coordinator.execute()

        self.assertFalse(result.success)
        self.assertEqual(result.failed_step, 1)
        self.assertEqual(result.steps[0].status, StepStatus.SUCCESS)
        self.assertEqual(result.steps[1].status, StepStatus.FAILED)
        self.assertEqual(result.steps[2].status, StepStatus.SKIPPED)

    @patch("cortex.coordinator.run_command")
    def test_execute_continue_on_error(self, mock_run_cmd, mock_sleep):
        def side_effect(cmd, *args, **kwargs):
            if "fail" in cmd:
                return CommandResult(success=False, stdout="", stderr="error", return_code=1, command=cmd)
            else:
                return CommandResult(success=True, stdout="success", stderr="", return_code=0, command=cmd)

        mock_run_cmd.side_effect = side_effect

        coordinator = InstallationCoordinator(["echo 1", "fail", "echo 3"], stop_on_error=False)
        result = coordinator.execute()

        self.assertFalse(result.success)
        self.assertEqual(result.steps[0].status, StepStatus.SUCCESS)
        self.assertEqual(result.steps[1].status, StepStatus.FAILED)
        self.assertEqual(result.steps[2].status, StepStatus.SUCCESS)

    @patch("cortex.coordinator.run_command")
    def test_timeout_handling(self, mock_run_cmd, mock_sleep):
        mock_run_cmd.side_effect = Exception("Timeout")

        coordinator = InstallationCoordinator(["sleep 1000"], timeout=1)
        result = coordinator.execute()

        self.assertFalse(result.success)
        self.assertEqual(result.steps[0].status, StepStatus.FAILED)

    def test_progress_callback(self, mock_sleep):
        callback_calls = []

        def callback(current, total, step):
            callback_calls.append((current, total, step.command))

        with patch("cortex.coordinator.run_command") as mock_run:
            mock_result = CommandResult(
                success=True, stdout="success", stderr="", return_code=0, command="echo test"
            )
            mock_run.return_value = mock_result

            coordinator = InstallationCoordinator(["echo 1", "echo 2"], progress_callback=callback)
            coordinator.execute()

        self.assertEqual(len(callback_calls), 2)
        self.assertEqual(callback_calls[0], (1, 2, "echo 1"))
        self.assertEqual(callback_calls[1], (2, 2, "echo 2"))

    def test_log_file(self, mock_sleep):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            log_file = f.name

        try:
            with patch("cortex.coordinator.run_command") as mock_run:
                mock_result = CommandResult(
                    success=True, stdout="success", stderr="", return_code=0, command="echo test"
                )
                mock_run.return_value = mock_result

                coordinator = InstallationCoordinator(["echo test"], log_file=log_file)
                coordinator.execute()

            self.assertTrue(os.path.exists(log_file))
            with open(log_file) as f:
                content = f.read()
                self.assertIn("Executing: echo test", content)
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    @patch("cortex.coordinator.run_command")
    def test_rollback(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=False, stdout="", stderr="error", return_code=1, command="fail"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["fail"], enable_rollback=True)
        coordinator.add_rollback_command("echo rollback")
        result = coordinator.execute()

        self.assertFalse(result.success)
        self.assertGreaterEqual(mock_run_cmd.call_count, 2)

    @patch("cortex.coordinator.run_command")
    def test_verify_installation(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=True, stdout="Docker version 20.10.0", stderr="", return_code=0, command="docker --version"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["echo test"])
        coordinator.execute()

        verify_results = coordinator.verify_installation(["docker --version"])

        self.assertTrue(verify_results["docker --version"])

    def test_get_summary(self, mock_sleep):
        with patch("cortex.coordinator.run_command") as mock_run:
            mock_result = CommandResult(
                success=True, stdout="success", stderr="", return_code=0, command="echo test"
            )
            mock_run.return_value = mock_result

            coordinator = InstallationCoordinator(["echo 1", "echo 2"])
            coordinator.execute()

            summary = coordinator.get_summary()

            self.assertEqual(summary["total_steps"], 2)
            self.assertEqual(summary["success"], 2)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(summary["skipped"], 0)

    def test_export_log(self, mock_sleep):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            export_file = f.name

        try:
            with patch("cortex.coordinator.run_command") as mock_run:
                mock_result = CommandResult(
                    success=True, stdout="success", stderr="", return_code=0, command="echo test"
                )
                mock_run.return_value = mock_result

                coordinator = InstallationCoordinator(["echo test"])
                coordinator.execute()
                coordinator.export_log(export_file)

            self.assertTrue(os.path.exists(export_file))

            import json

            with open(export_file) as f:
                data = json.load(f)
                self.assertIn("total_steps", data)
                self.assertEqual(data["total_steps"], 1)
        finally:
            if os.path.exists(export_file):
                os.unlink(export_file)

    @patch("cortex.coordinator.run_command")
    def test_step_timing(self, mock_run_cmd, mock_sleep):
        mock_result = CommandResult(
            success=True, stdout="success", stderr="", return_code=0, command="echo test"
        )
        mock_run_cmd.return_value = mock_result

        coordinator = InstallationCoordinator(["echo test"])
        result = coordinator.execute()

        step = result.steps[0]
        self.assertIsNotNone(step.start_time)
        self.assertIsNotNone(step.end_time)
        if step.end_time and step.start_time:
            self.assertGreater(step.end_time, step.start_time)
        self.assertIsNotNone(step.duration())


class TestInstallDocker(unittest.TestCase):
    @patch("cortex.coordinator.run_command")
    def test_install_docker_success(self, mock_run_cmd):
        mock_result = CommandResult(
            success=True, stdout="success", stderr="", return_code=0, command="apt update"
        )
        mock_run_cmd.return_value = mock_result

        result = install_docker()

        self.assertTrue(result.success)
        self.assertEqual(len(result.steps), 10)

    @patch("cortex.coordinator.run_command")
    def test_install_docker_failure(self, mock_run_cmd):
        mock_result = CommandResult(
            success=False, stdout="", stderr="error", return_code=1, command="apt update"
        )
        mock_run_cmd.return_value = mock_result

        result = install_docker()

        self.assertFalse(result.success)
        self.assertIsNotNone(result.failed_step)


class TestInstallationPlans(unittest.TestCase):
    def test_example_cuda_install_plan_structure(self):
        plan = example_cuda_install_plan()

        self.assertGreaterEqual(len(plan), 5)
        self.assertTrue(all("command" in step for step in plan))
        self.assertTrue(any("rollback" in step for step in plan))


if __name__ == "__main__":
    unittest.main()
