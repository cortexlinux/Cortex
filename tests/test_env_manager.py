#!/usr/bin/env python3
"""
Comprehensive tests for Environment Manager
Tests all environment management features including encryption, validation, templates
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortex.env_manager import (
    EnvManager,
    EnvTemplate,
    EnvVariable,
    RegexValidator,
    RequiredValidator,
    URLValidator,
)


class TestEnvVariable(unittest.TestCase):
    """Test EnvVariable dataclass"""

    def test_creation(self):
        """Test variable creation"""
        var = EnvVariable(key="TEST_KEY", value="test_value")
        self.assertEqual(var.key, "TEST_KEY")
        self.assertEqual(var.value, "test_value")
        self.assertFalse(var.encrypted)
        self.assertEqual(var.description, "")
        self.assertIsNotNone(var.created_at)
        self.assertIsNotNone(var.updated_at)

    def test_to_dict(self):
        """Test conversion to dictionary"""
        var = EnvVariable(
            key="API_KEY", value="secret", encrypted=True, description="API key"
        )
        data = var.to_dict()
        self.assertEqual(data["key"], "API_KEY")
        self.assertEqual(data["value"], "secret")
        self.assertTrue(data["encrypted"])
        self.assertEqual(data["description"], "API key")

    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            "key": "DATABASE_URL",
            "value": "postgres://localhost/db",
            "encrypted": False,
            "description": "Database connection",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "tags": ["database"],
        }
        var = EnvVariable.from_dict(data)
        self.assertEqual(var.key, "DATABASE_URL")
        self.assertEqual(var.value, "postgres://localhost/db")
        self.assertFalse(var.encrypted)
        self.assertEqual(var.description, "Database connection")
        self.assertEqual(var.tags, ["database"])


class TestEnvTemplate(unittest.TestCase):
    """Test EnvTemplate dataclass"""

    def test_creation(self):
        """Test template creation"""
        template = EnvTemplate(
            name="django",
            description="Django environment",
            variables={"SECRET_KEY": "change-me", "DEBUG": "False"},
            required_vars=["SECRET_KEY"],
        )
        self.assertEqual(template.name, "django")
        self.assertEqual(template.description, "Django environment")
        self.assertEqual(len(template.variables), 2)
        self.assertEqual(template.required_vars, ["SECRET_KEY"])

    def test_to_from_dict(self):
        """Test conversion to/from dictionary"""
        template = EnvTemplate(
            name="test", description="Test template", variables={"KEY": "value"}
        )
        data = template.to_dict()
        restored = EnvTemplate.from_dict(data)
        self.assertEqual(restored.name, template.name)
        self.assertEqual(restored.description, template.description)
        self.assertEqual(restored.variables, template.variables)


class TestValidators(unittest.TestCase):
    """Test validation rules"""

    def test_regex_validator(self):
        """Test regex validation"""
        validator = RegexValidator(r"^[0-9]+$", "Must be numeric")
        
        # Valid
        is_valid, error = validator.validate("PORT", "3000")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Invalid
        is_valid, error = validator.validate("PORT", "abc")
        self.assertFalse(is_valid)
        self.assertIn("Must be numeric", error)

    def test_url_validator(self):
        """Test URL validation"""
        validator = URLValidator()
        
        # Valid URLs
        valid_urls = [
            "http://localhost",
            "https://example.com",
            "http://192.168.1.1:8080",
            "https://api.example.com/v1/endpoint",
            "postgres://localhost/db",
            "mysql://localhost:3306/mydb",
        ]
        for url in valid_urls:
            is_valid, error = validator.validate("URL", url)
            self.assertTrue(is_valid, f"Failed for {url}")
        
        # Invalid URLs
        invalid_urls = [
            "not-a-url",
            "example.com",  # Missing protocol
        ]
        for url in invalid_urls:
            is_valid, error = validator.validate("URL", url)
            self.assertFalse(is_valid, f"Should fail for {url}")

    def test_required_validator(self):
        """Test required field validation"""
        validator = RequiredValidator()
        
        # Valid
        is_valid, error = validator.validate("KEY", "value")
        self.assertTrue(is_valid)
        
        # Invalid
        for value in ["", "   ", None]:
            if value is None:
                continue  # Skip None as it would fail type check
            is_valid, error = validator.validate("KEY", value)
            self.assertFalse(is_valid)


class TestEnvManager(unittest.TestCase):
    """Test EnvManager functionality"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.manager = EnvManager(cortex_home=self.test_dir)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)

    def test_init(self):
        """Test manager initialization"""
        self.assertTrue(self.manager.env_dir.exists())
        self.assertTrue(self.manager.templates_dir.exists())
        self.assertTrue(self.manager.key_file.exists())

    def test_set_and_get_variable(self):
        """Test setting and getting variables"""
        self.manager.set("myapp", "DATABASE_URL", "postgres://localhost/mydb")
        value = self.manager.get("myapp", "DATABASE_URL")
        self.assertEqual(value, "postgres://localhost/mydb")

    def test_encrypted_variable(self):
        """Test encrypted variable storage"""
        original = "secret_api_key_12345"
        self.manager.set("myapp", "API_KEY", original, encrypt=True)
        
        # Get decrypted value
        decrypted = self.manager.get("myapp", "API_KEY", decrypt=True)
        self.assertEqual(decrypted, original)
        
        # Get encrypted value (raw)
        encrypted = self.manager.get("myapp", "API_KEY", decrypt=False)
        self.assertNotEqual(encrypted, original)
        self.assertTrue(len(encrypted) > len(original))

    def test_update_variable(self):
        """Test updating existing variable"""
        self.manager.set("myapp", "PORT", "3000")
        self.manager.set("myapp", "PORT", "8080")
        
        value = self.manager.get("myapp", "PORT")
        self.assertEqual(value, "8080")

    def test_delete_variable(self):
        """Test deleting variables"""
        self.manager.set("myapp", "TEMP_VAR", "temp_value")
        
        # Delete existing
        result = self.manager.delete("myapp", "TEMP_VAR")
        self.assertTrue(result)
        
        # Verify deleted
        value = self.manager.get("myapp", "TEMP_VAR")
        self.assertIsNone(value)
        
        # Delete non-existent
        result = self.manager.delete("myapp", "TEMP_VAR")
        self.assertFalse(result)

    def test_list_variables(self):
        """Test listing variables"""
        self.manager.set("myapp", "VAR1", "value1")
        self.manager.set("myapp", "VAR2", "value2", encrypt=True)
        
        env_vars = self.manager.list("myapp")
        self.assertEqual(len(env_vars), 2)
        self.assertIn("VAR1", env_vars)
        self.assertIn("VAR2", env_vars)
        self.assertFalse(env_vars["VAR1"].encrypted)
        self.assertTrue(env_vars["VAR2"].encrypted)

    def test_list_apps(self):
        """Test listing applications"""
        self.manager.set("app1", "KEY", "value")
        self.manager.set("app2", "KEY", "value")
        self.manager.set("app3", "KEY", "value")
        
        apps = self.manager.list_apps()
        self.assertEqual(len(apps), 3)
        self.assertIn("app1", apps)
        self.assertIn("app2", apps)
        self.assertIn("app3", apps)

    def test_export_env_format(self):
        """Test export in .env format"""
        self.manager.set("myapp", "DATABASE_URL", "postgres://localhost/db")
        self.manager.set("myapp", "API_KEY", "secret123", encrypt=True)
        self.manager.set("myapp", "PORT", "3000")
        
        output = self.manager.export("myapp", format="env")
        
        self.assertIn('export DATABASE_URL="postgres://localhost/db"', output)
        self.assertIn('export API_KEY="[encrypted]"', output)
        self.assertIn('export PORT="3000"', output)

    def test_export_json_format(self):
        """Test export in JSON format"""
        self.manager.set("myapp", "DATABASE_URL", "postgres://localhost/db")
        self.manager.set("myapp", "SECRET", "secret123", encrypt=True)
        
        output = self.manager.export("myapp", format="json")
        data = json.loads(output)
        
        self.assertEqual(data["DATABASE_URL"], "postgres://localhost/db")
        self.assertEqual(data["SECRET"], "[encrypted]")

    def test_export_yaml_format(self):
        """Test export in YAML format"""
        self.manager.set("myapp", "KEY1", "value1")
        self.manager.set("myapp", "KEY2", "value2")
        
        output = self.manager.export("myapp", format="yaml")
        
        self.assertIn('KEY1: "value1"', output)
        self.assertIn('KEY2: "value2"', output)

    def test_import_env_format(self):
        """Test import from .env format"""
        env_data = '''
        export DATABASE_URL="postgres://localhost/testdb"
        export API_KEY="test_key_123"
        # Comment line
        export PORT="8080"
        '''
        
        self.manager.import_env("myapp", env_data, format="env")
        
        self.assertEqual(self.manager.get("myapp", "DATABASE_URL"), "postgres://localhost/testdb")
        self.assertEqual(self.manager.get("myapp", "API_KEY"), "test_key_123")
        self.assertEqual(self.manager.get("myapp", "PORT"), "8080")

    def test_import_json_format(self):
        """Test import from JSON format"""
        env_data = json.dumps({
            "DATABASE_URL": "postgres://localhost/jsondb",
            "SECRET": "json_secret",
        })
        
        self.manager.import_env("myapp", env_data, format="json")
        
        self.assertEqual(self.manager.get("myapp", "DATABASE_URL"), "postgres://localhost/jsondb")
        self.assertEqual(self.manager.get("myapp", "SECRET"), "json_secret")

    def test_import_merge(self):
        """Test import with merge option"""
        # Set initial variables
        self.manager.set("myapp", "EXISTING", "keep_me")
        self.manager.set("myapp", "OVERRIDE", "old_value")
        
        # Import with merge
        env_data = 'export OVERRIDE="new_value"\nexport NEW_VAR="added"'
        self.manager.import_env("myapp", env_data, format="env", merge=True)
        
        # Existing var should remain
        self.assertEqual(self.manager.get("myapp", "EXISTING"), "keep_me")
        # Overridden var should update
        self.assertEqual(self.manager.get("myapp", "OVERRIDE"), "new_value")
        # New var should be added
        self.assertEqual(self.manager.get("myapp", "NEW_VAR"), "added")

    def test_import_replace(self):
        """Test import with replace (default)"""
        # Set initial variables
        self.manager.set("myapp", "OLD_VAR", "will_be_removed")
        
        # Import without merge
        env_data = 'export NEW_VAR="only_this"'
        self.manager.import_env("myapp", env_data, format="env", merge=False)
        
        # Old var should be gone
        self.assertIsNone(self.manager.get("myapp", "OLD_VAR"))
        # New var should exist
        self.assertEqual(self.manager.get("myapp", "NEW_VAR"), "only_this")

    def test_builtin_templates(self):
        """Test built-in templates are created"""
        templates = self.manager.list_templates()
        template_names = [t.name for t in templates]
        
        self.assertIn("nodejs", template_names)
        self.assertIn("python", template_names)
        self.assertIn("django", template_names)
        self.assertIn("docker", template_names)

    def test_get_template(self):
        """Test getting a specific template"""
        template = self.manager.get_template("nodejs")
        
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "nodejs")
        self.assertIn("NODE_ENV", template.variables)
        self.assertIn("PORT", template.variables)

    def test_create_custom_template(self):
        """Test creating custom template"""
        template = EnvTemplate(
            name="custom",
            description="Custom template",
            variables={"CUSTOM_VAR": "custom_value"},
            required_vars=["CUSTOM_VAR"],
        )
        
        self.manager.create_template(template)
        
        # Verify it can be retrieved
        retrieved = self.manager.get_template("custom")
        self.assertEqual(retrieved.name, "custom")
        self.assertEqual(retrieved.variables, {"CUSTOM_VAR": "custom_value"})

    def test_apply_template(self):
        """Test applying template to application"""
        # Apply nodejs template with custom values
        self.manager.apply_template(
            "myapp",
            "nodejs",
            variables={"DATABASE_URL": "postgres://localhost/mydb", "PORT": "5000"},
        )
        
        # Verify variables were set
        env_vars = self.manager.list("myapp")
        self.assertIn("NODE_ENV", env_vars)
        self.assertIn("DATABASE_URL", env_vars)
        self.assertEqual(self.manager.get("myapp", "DATABASE_URL"), "postgres://localhost/mydb")
        self.assertEqual(self.manager.get("myapp", "PORT"), "5000")

    def test_apply_template_missing_required(self):
        """Test applying template with missing required variables"""
        with self.assertRaises(ValueError) as context:
            self.manager.apply_template("myapp", "django", variables={})
        
        self.assertIn("Missing required variables", str(context.exception))

    def test_validation_url(self):
        """Test URL validation"""
        # Valid URL
        is_valid, error = self.manager.validate("DATABASE_URL", "postgres://localhost/db")
        self.assertTrue(is_valid)
        
        # Invalid URL
        is_valid, error = self.manager.validate("API_URL", "not-a-url")
        self.assertFalse(is_valid)

    def test_validation_required(self):
        """Test required field validation"""
        # API keys should not be empty
        is_valid, error = self.manager.validate("API_KEY", "some_key")
        self.assertTrue(is_valid)
        
        is_valid, error = self.manager.validate("MY_API_KEY", "")
        self.assertFalse(is_valid)

    def test_validation_port(self):
        """Test port validation"""
        # Valid ports
        for port in ["80", "443", "3000", "8080", "65535"]:
            is_valid, error = self.manager.validate("PORT", port)
            self.assertTrue(is_valid, f"Port {port} should be valid")
        
        # Invalid ports
        for port in ["0", "abc", "70000", "-1"]:
            is_valid, error = self.manager.validate("PORT", port)
            self.assertFalse(is_valid, f"Port {port} should be invalid")

    def test_set_with_validation_failure(self):
        """Test that set fails with invalid values"""
        with self.assertRaises(ValueError):
            self.manager.set("myapp", "DATABASE_URL", "not-a-url")

    def test_get_env_dict(self):
        """Test getting environment as dictionary"""
        self.manager.set("myapp", "VAR1", "value1")
        self.manager.set("myapp", "VAR2", "value2", encrypt=True)
        
        # Get decrypted dict
        env_dict = self.manager.get_env_dict("myapp", decrypt=True)
        self.assertEqual(env_dict["VAR1"], "value1")
        self.assertEqual(env_dict["VAR2"], "value2")
        
        # Get with encrypted values
        env_dict = self.manager.get_env_dict("myapp", decrypt=False)
        self.assertEqual(env_dict["VAR1"], "value1")
        self.assertNotEqual(env_dict["VAR2"], "value2")  # Should be encrypted

    def test_load_env_to_os(self):
        """Test loading environment to os.environ"""
        self.manager.set("myapp", "TEST_VAR_1", "test_value_1")
        self.manager.set("myapp", "TEST_VAR_2", "test_value_2")
        
        # Load to os.environ
        self.manager.load_env_to_os("myapp")
        
        self.assertEqual(os.environ.get("TEST_VAR_1"), "test_value_1")
        self.assertEqual(os.environ.get("TEST_VAR_2"), "test_value_2")
        
        # Clean up
        del os.environ["TEST_VAR_1"]
        del os.environ["TEST_VAR_2"]

    def test_delete_app(self):
        """Test deleting entire application environment"""
        self.manager.set("myapp", "VAR1", "value1")
        self.manager.set("myapp", "VAR2", "value2")
        
        # Delete app
        result = self.manager.delete_app("myapp")
        self.assertTrue(result)
        
        # Verify app is gone
        env_vars = self.manager.list("myapp")
        self.assertEqual(len(env_vars), 0)
        
        # Delete non-existent app
        result = self.manager.delete_app("nonexistent")
        self.assertFalse(result)

    def test_variable_metadata(self):
        """Test variable description and tags"""
        self.manager.set(
            "myapp",
            "API_KEY",
            "secret123",
            description="Production API key",
            tags=["production", "api"],
        )
        
        env_vars = self.manager.list("myapp")
        var = env_vars["API_KEY"]
        
        self.assertEqual(var.description, "Production API key")
        self.assertEqual(var.tags, ["production", "api"])

    def test_encryption_consistency(self):
        """Test that encryption/decryption is consistent"""
        test_values = [
            "simple_value",
            "complex!@#$%^&*()value",
            "unicode_表情符号_test",
            "long_" + ("x" * 1000),
        ]
        
        for original in test_values:
            self.manager.set("testapp", "TEST_VAR", original, encrypt=True)
            decrypted = self.manager.get("testapp", "TEST_VAR", decrypt=True)
            self.assertEqual(decrypted, original, f"Failed for: {original[:50]}")

    def test_file_permissions(self):
        """Test that sensitive files have correct permissions"""
        self.manager.set("myapp", "SECRET", "secret_value")
        
        # Check key file permissions (should be 0o600)
        key_stat = self.manager.key_file.stat()
        self.assertEqual(oct(key_stat.st_mode)[-3:], "600")
        
        # Check env file permissions (should be 0o600)
        app_file = self.manager._get_app_file("myapp")
        app_stat = app_file.stat()
        self.assertEqual(oct(app_stat.st_mode)[-3:], "600")


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.manager = EnvManager(cortex_home=self.test_dir)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)

    def test_complete_workflow(self):
        """Test a complete workflow"""
        # Apply template
        self.manager.apply_template(
            "webapp",
            "django",
            variables={
                "SECRET_KEY": "django-secret-key-123",
                "DATABASE_URL": "postgres://localhost/webapp",
            },
        )
        
        # Add custom variables
        self.manager.set("webapp", "STRIPE_KEY", "sk_test_123", encrypt=True)
        self.manager.set("webapp", "CACHE_URL", "redis://localhost:6379")
        
        # Export to file
        output = self.manager.export("webapp", format="env")
        self.assertIn("SECRET_KEY", output)
        self.assertIn("DATABASE_URL", output)
        self.assertIn("STRIPE_KEY", output)
        
        # List and verify
        env_vars = self.manager.list("webapp")
        self.assertGreater(len(env_vars), 3)
        
        # Verify encrypted variable
        stripe_key = self.manager.get("webapp", "STRIPE_KEY", decrypt=True)
        self.assertEqual(stripe_key, "sk_test_123")


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestEnvVariable))
    suite.addTests(loader.loadTestsFromTestCase(TestEnvTemplate))
    suite.addTests(loader.loadTestsFromTestCase(TestValidators))
    suite.addTests(loader.loadTestsFromTestCase(TestEnvManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
