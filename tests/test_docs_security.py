from unittest.mock import patch

import pytest

from cortex.docs_generator import DocsGenerator


def test_path_sanitization_robust():
    """Verify that software names are sanitized into safe forms."""
    gen = DocsGenerator()

    # Test cases that should be sanitized
    test_cases = [
        ("../../etc/passwd", "etc_passwd"),
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


def test_path_traversal_detection():
    """Verify that explicit path traversal attempts are detected by parent check."""
    gen = DocsGenerator()

    # We patch _sanitize_name to return malicious raw strings to test the parent check in _get_software_dir
    with patch.object(gen, "_sanitize_name", side_effect=lambda x: x):
        malicious_names = [
            "/tmp/evil",
            "../../etc",
            "../docs",  # resolved path is docs_dir itself, which is not a child of docs_dir.parents
        ]
        for name in malicious_names:
            with pytest.raises(ValueError) as excinfo:
                gen._get_software_dir(name)
            assert "path escape attempt" in str(excinfo.value)


def test_export_format_validation():
    """Verify that illegal export formats are blocked."""
    gen = DocsGenerator()
    malicious_formats = [
        "../../tmp/pwned",
        "doc.exe",
        "php",
        "/etc/passwd",
        "",
        " ",
    ]

    for fmt in malicious_formats:
        with pytest.raises(ValueError) as excinfo:
            gen.export_docs("nginx", format=fmt)
        assert "Unsupported or invalid export format" in str(excinfo.value)


def test_safe_software_name():
    """Verify that legitimate software names are accepted."""
    gen = DocsGenerator()
    try:
        gen._sanitize_name("postgresql")
        gen._sanitize_name("nginx-common")
        gen._sanitize_name("python3.12")
        gen._sanitize_name("libssl1.1")
    except ValueError:
        pytest.fail("Legitimate software name raised ValueError")
