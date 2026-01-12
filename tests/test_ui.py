"""Tests for Cortex UI module."""
import pytest
from cortex.ui.theme import COLORS, SYMBOLS, CORTEX_THEME, PANEL_STYLES
from cortex.ui.console import console, CortexConsole
from cortex.ui.prompts import CommandPrompt, MenuAction, PromptResult, COMMAND_MENU_OPTIONS
from cortex.ui.progress import StepsProgress
from cortex.ui.trust import TrustManager, TrustScope
from cortex.ui.explain import parse_command, get_explanation
from cortex.ui.errors import auto_suggest_fix, COMMON_ERRORS


class TestTheme:
    def test_colors_defined(self):
        for color in ["success", "error", "warning", "info", "command", "secondary", "primary", "cortex"]:
            assert color in COLORS
    
    def test_symbols_defined(self):
        for symbol in ["success", "error", "warning", "info", "command", "thinking", "step", "prompt"]:
            assert symbol in SYMBOLS


class TestConsole:
    def test_singleton(self):
        assert CortexConsole() is CortexConsole()
    
    def test_message_methods(self):
        for method in ["success", "error", "warning", "info", "command", "step", "thinking", "secondary"]:
            assert callable(getattr(console, method))


class TestPrompts:
    def test_menu_options_complete(self):
        assert len(COMMAND_MENU_OPTIONS) == 6
        actions = {opt.action for opt in COMMAND_MENU_OPTIONS}
        assert actions == {MenuAction.RUN, MenuAction.TRUST, MenuAction.DRY_RUN, MenuAction.EXPLAIN, MenuAction.EDIT, MenuAction.CANCEL}
    
    def test_command_prompt_init(self):
        prompt = CommandPrompt(command="docker run nginx", context="Deploy nginx")
        assert prompt.command == "docker run nginx"


class TestTrust:
    def test_command_type_extraction(self):
        manager = TrustManager()
        assert manager._get_command_type("docker run -d nginx") == "docker run"
        assert manager._get_command_type("git commit -m 'test'") == "git commit"


class TestExplain:
    def test_parse_command(self):
        base, args = parse_command("docker run -d nginx")
        assert base == "docker"
        assert args == ["run", "-d", "nginx"]


class TestErrors:
    def test_auto_suggest_container_conflict(self):
        fix = auto_suggest_fix('container name "/ollama" already in use')
        assert fix is not None
        assert "docker rm" in fix.command


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
