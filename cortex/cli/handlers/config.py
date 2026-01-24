"""Config command handler for Cortex CLI.

Provides configuration management for language and settings.
"""

import argparse

from cortex.i18n import get_language, set_language, SUPPORTED_LANGUAGES


class ConfigHandler:
    """Handler for config command."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def config(self, args: argparse.Namespace) -> int:
        """Handle config command."""
        if hasattr(args, 'language') and args.language:
            return self._config_language(args.language)
        return self._config_show()

    def _config_language(self, language: str) -> int:
        """Set the language for CLI."""
        if language not in SUPPORTED_LANGUAGES:
            print(f"Error: Language '{language}' not supported.")
            print(f"Available languages: {', '.join(SUPPORTED_LANGUAGES.keys())}")
            return 1

        set_language(language)
        print(f"Language set to {SUPPORTED_LANGUAGES[language]['name']}")
        return 0

    def _config_show(self) -> int:
        """Show current configuration."""
        current_lang = get_language()
        lang_info = SUPPORTED_LANGUAGES.get(current_lang, {})
        print(f"Current language: {lang_info.get('name', current_lang)}")
        return 0


def add_config_parser(subparsers) -> argparse.ArgumentParser:
    """Add config parser to subparsers."""
    config_parser = subparsers.add_parser("config", help="Configure Cortex settings")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    language_parser = config_subparsers.add_parser("language", help="Set CLI language")
    language_parser.add_argument("language", help="Language code (e.g., en, es, fr)")

    show_parser = config_subparsers.add_parser("show", help="Show current configuration")

    return config_parser
