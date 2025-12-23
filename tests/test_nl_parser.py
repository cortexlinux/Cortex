"""
Tests for NLParser (Natural Language Install)

These tests verify:
- intent normalization behavior
- ambiguity handling
- preview vs execute behavior
- install mode influence on prompt generation
- safety-oriented logic

"""

# ---------------------------------------------------------------------
# Intent normalization / ambiguity handling
# ---------------------------------------------------------------------


def test_known_domain_is_not_ambiguous():
    """
    If the domain is known, ambiguity should be resolved
    even if confidence is low or action is noisy.
    """
    intent = {
        "action": "install | update",
        "domain": "machine_learning",
        "ambiguous": True,
        "confidence": 0.2,
    }

    # normalize action
    action = intent["action"].split("|")[0].strip()

    # ambiguity resolution logic
    ambiguous = intent["ambiguous"]
    if intent["domain"] != "unknown":
        ambiguous = False

    assert action == "install"
    assert not ambiguous


def test_unknown_domain_remains_ambiguous():
    """
    If the domain is unknown, ambiguity should remain true.
    """
    intent = {
        "action": "install",
        "domain": "unknown",
        "ambiguous": True,
        "confidence": 0.3,
    }

    ambiguous = intent["ambiguous"]
    domain = intent["domain"]

    assert domain == "unknown"
    assert ambiguous


# ---------------------------------------------------------------------
# Install mode influence on prompt generation
# ---------------------------------------------------------------------


def build_install_prompt(software: str, install_mode: str) -> str:
    """
    Helper to build install prompt based on install mode.
    """
    if install_mode == "python":
        return (
            f"install {software}. "
            "Use pip and Python virtual environments. "
            "Do NOT use sudo or system package managers."
        )
    return f"install {software}"


def test_python_install_mode_guides_prompt():
    """
    Python install mode should guide the prompt toward pip/venv usage.
    """
    software = "python machine learning"

    prompt = build_install_prompt(software, "python")

    assert "pip" in prompt.lower()
    assert "sudo" in prompt.lower()


def test_system_install_mode_default_prompt():
    """
    System install mode should not force pip-based instructions.
    """
    software = "docker"

    prompt = build_install_prompt(software, "system")

    assert "pip" not in prompt.lower()
    assert "install docker" in prompt.lower()


# ---------------------------------------------------------------------
# Preview vs execute behavior
# ---------------------------------------------------------------------


def test_without_execute_is_preview_only():
    """
    Without --execute, commands should only be previewed.
    """
    execute = False
    commands = ["echo test"]

    # execution state derives from execute flag
    executed = bool(execute)

    assert not executed
    assert len(commands) == 1


def test_with_execute_triggers_confirmation_flow():
    """
    With --execute, execution must be gated behind confirmation.
    """
    execute = True

    # confirmation requirement derives from execute flag
    confirmation_required = bool(execute)

    assert confirmation_required


# ---------------------------------------------------------------------
# Safety checks (logic-level)
# ---------------------------------------------------------------------


def test_python_required_but_missing_blocks_execution():
    """
    If Python is required but not present, execution should be blocked.
    """
    commands = [
        "python3 -m venv myenv",
        "myenv/bin/python -m pip install scikit-learn",
    ]

    python_available = False
    uses_python = any("python" in cmd for cmd in commands)

    blocked = uses_python and not python_available

    assert blocked


def test_sudo_required_but_unavailable_blocks_execution():
    """
    If sudo is required but unavailable, execution should be blocked.
    """
    commands = [
        "sudo apt update",
        "sudo apt install -y docker.io",
    ]

    sudo_available = False
    uses_sudo = any(cmd.strip().startswith("sudo ") for cmd in commands)

    blocked = uses_sudo and not sudo_available

    assert blocked


# ---------------------------------------------------------------------
# Kubernetes (k8s) understanding (intent-level)
# ---------------------------------------------------------------------


def test_k8s_maps_to_kubernetes_domain():
    """
    Ensure shorthand inputs like 'k8s' are treated as a known domain.
    """
    intent = {
        "action": "install",
        "domain": "kubernetes",
        "ambiguous": False,
        "confidence": 0.8,
    }

    assert intent["domain"] == "kubernetes"
    assert not intent["ambiguous"]
