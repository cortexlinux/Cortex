from unittest.mock import MagicMock, patch

import pytest

from cortex.docs_generator import DocsGenerator


@pytest.fixture
def gen(tmp_path):
    """Fixture to provide a DocsGenerator with a safe, isolated docs_dir."""
    docs_dir = tmp_path / "cortex_docs_test"
    docs_dir.mkdir()
    generator = DocsGenerator()
    generator.docs_dir = docs_dir
    return generator


def test_path_sanitization_robust(gen):
    """Verify that software names are sanitized into safe forms."""
    # Test cases that should be sanitized
    test_cases = [
        ("../../outside/secret", "outside_secret"),
        ("nginx; rm -rf", "nginx__rm_-rf"),
        ("pkg*name", "pkg_name"),
        ("pkg$name", "pkg_name"),
        (".hidden", "hidden"),
        ("trailing.", "trailing"),
        ("__leading", "leading"),
    ]

    for input_name, expected_safe in test_cases:
        safe = gen._sanitize_name(input_name)
        assert safe == expected_safe

    # Test cases that must raise ValueError (empty after sanitization or inherently invalid)
    invalid_cases = [
        "",
        " ",
        "!!!",
        "...///...",
        "..",
        ".",
        "/",
        "\\",
    ]
    for name in invalid_cases:
        with pytest.raises(ValueError):
            gen._sanitize_name(name)


def test_path_traversal_detection(gen, tmp_path):
    """Verify that explicit path traversal attempts are detected by parent check."""
    # We patch _sanitize_name to return malicious raw strings to test the parent check in _get_software_dir
    with patch.object(gen, "_sanitize_name", side_effect=lambda x: x):
        malicious_names = [
            str(tmp_path / "outside_dir"),
            "../../outside_cortex",
            "../cortex_docs_test",  # resolved path is docs_dir itself, not a child
        ]
        for name in malicious_names:
            with pytest.raises(ValueError) as excinfo:
                gen._get_software_dir(name)
            assert "path escape attempt" in str(excinfo.value)


def test_export_docs_path_traversal_bypass(gen, tmp_path):
    """Verify that export_docs name bypass is fixed using safe temp paths."""
    # A path that would try to escape the test isolated docs_dir
    outside_target = str(tmp_path / "not_docs" / "pwned")
    malicious_name = f"../../../{outside_target}"

    # We expect sanitized output: "not_docs_pwned_docs.md" in current dir
    # NOT escaping to the outside_target
    with patch.object(gen, "generate_software_docs") as mock_gen_docs:
        with patch("builtins.open", MagicMock()) as mock_open:
            with patch("os.listdir", return_value=[]):
                # Should NOT raise ValueError if sanitization works
                gen.export_docs(malicious_name, format="md")

                # Check for sanitized name in Path.cwd() calls
                found_safe_path = False
                for call in mock_open.call_args_list:
                    path_arg = str(call[0][0])
                    # Sanitized version of malicious_name should appear
                    if "not_docs_pwned_docs.md" in path_arg:
                        found_safe_path = True
                    # The raw outside_target should NOT appear
                    if "not_docs/pwned" in path_arg:
                        pytest.fail(
                            f"VULNERABILITY: Export path used unsanitized input: {path_arg}"
                        )

                assert found_safe_path, "Export path with sanitized name was not opened"


def test_export_format_validation(gen):
    """Verify that illegal export formats are blocked."""
    malicious_formats = [
        "../../safe_temp/pwned",
        "doc.exe",
        "php",
        "../../../../etc/passwd",
        "",
        " ",
    ]

    for fmt in malicious_formats:
        with pytest.raises(ValueError) as excinfo:
            gen.export_docs("nginx", format=fmt)
        assert "Unsupported or invalid export format" in str(excinfo.value)


def test_safe_software_name(gen):
    """Verify that legitimate software names are accepted."""
    try:
        gen._sanitize_name("postgresql")
        gen._sanitize_name("nginx-common")
        gen._sanitize_name("python3.12")
        gen._sanitize_name("libssl1.1")
    except ValueError:
        pytest.fail("Legitimate software name raised ValueError")
