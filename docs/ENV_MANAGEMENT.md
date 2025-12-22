# Environment Variable Management

Cortex provides comprehensive environment variable management for applications and services with built-in encryption, templates, and validation.

## Features

- **Per-Application Isolation**: Each application has its own isolated environment
- **Encrypted Storage**: Sensitive values are encrypted at rest
- **Environment Templates**: Quick setup for common frameworks (Django, Node.js, etc.)
- **Variable Validation**: Automatic validation for URLs, ports, and required fields
- **Auto-Load on Service Start**: Easily load environment variables into your applications
- **Import/Export**: Share environments across systems

## Quick Start

### Set Environment Variables

```bash
# Set a simple variable
cortex env set myapp DATABASE_URL "postgres://localhost/mydb"

# Set an encrypted variable
cortex env set myapp API_KEY "secret123" --encrypt

# Set with description and tags
cortex env set myapp STRIPE_KEY "sk_live_..." --encrypt \
  --description "Production Stripe API key" \
  --tags production payment
```

### List Variables

```bash
# List all applications
cortex env list

# List variables for a specific app
cortex env list myapp
```

Output:
```
🔧 Environment variables for myapp:

  DATABASE_URL: postgres://localhost/mydb
  API_KEY: [encrypted] 🔐
    Production API key
  NODE_ENV: production
```

### Get a Variable

```bash
# Get variable value
cortex env get myapp DATABASE_URL
```

### Delete Variables

```bash
# Delete a single variable
cortex env delete myapp TEMP_VAR

# Clear all variables for an app
cortex env clear myapp
```

## Export and Import

### Export to File

```bash
# Export as .env file (default)
cortex env export myapp > myapp.env

# Export as JSON
cortex env export myapp --format json > myapp.json

# Export as YAML
cortex env export myapp --format yaml > myapp.yaml
```

### Import from File

```bash
# Import from .env file
cortex env import myapp myapp.env

# Import from JSON
cortex env import myapp config.json --format json

# Merge with existing variables
cortex env import myapp additional.env --merge
```

## Environment Templates

Cortex includes built-in templates for common frameworks and use cases.

### List Available Templates

```bash
cortex env template list
```

Output:
```
📋 Available templates:

  nodejs
    Node.js application environment
    Variables: NODE_ENV, PORT, DATABASE_URL, REDIS_URL, LOG_LEVEL
    Required: DATABASE_URL

  python
    Python application environment
    Variables: PYTHON_ENV, DATABASE_URL, REDIS_URL, LOG_LEVEL, DEBUG
    Required: DATABASE_URL

  django
    Django application environment
    Variables: DJANGO_SETTINGS_MODULE, SECRET_KEY, DEBUG, DATABASE_URL, ALLOWED_HOSTS
    Required: SECRET_KEY, DATABASE_URL

  docker
    Docker environment variables
    Variables: DOCKER_HOST, COMPOSE_PROJECT_NAME, COMPOSE_FILE
```

### Apply a Template

```bash
# Apply template with required variables
cortex env template apply myapp django \
  --var SECRET_KEY="your-secret-key-here" \
  --var DATABASE_URL="postgres://localhost/mydb"

# Override default values
cortex env template apply myapp nodejs \
  --var DATABASE_URL="postgres://prod-db/myapp" \
  --var PORT="5000" \
  --var NODE_ENV="production"
```

## Validation Rules

Cortex automatically validates environment variables based on naming patterns:

### URL Validation
Variables ending in `_URL` are validated as URLs:
```bash
# Valid
cortex env set myapp DATABASE_URL "postgres://localhost/db"
cortex env set myapp API_URL "https://api.example.com"

# Invalid - will fail
cortex env set myapp DATABASE_URL "not-a-url"
```

### Port Validation
Variables containing `PORT` are validated as port numbers (1-65535):
```bash
# Valid
cortex env set myapp PORT "3000"
cortex env set myapp REDIS_PORT "6379"

# Invalid - will fail
cortex env set myapp PORT "70000"
cortex env set myapp PORT "abc"
```

### Required Fields
Variables containing `API_KEY`, `SECRET`, or `DATABASE` cannot be empty:
```bash
# Valid
cortex env set myapp API_KEY "sk_live_123..."

# Invalid - will fail
cortex env set myapp API_KEY ""
```

## Using Environment Variables in Applications

### Python Applications

```python
from cortex.env_manager import EnvManager

# Load environment variables
manager = EnvManager()
manager.load_env_to_os("myapp")

# Now access via os.environ
import os
database_url = os.environ.get("DATABASE_URL")
api_key = os.environ.get("API_KEY")
```

### Shell Scripts

```bash
# Export variables to current shell
eval "$(cortex env export myapp)"

# Use variables
echo $DATABASE_URL
curl -H "Authorization: Bearer $API_KEY" https://api.example.com
```

### Docker Compose

```bash
# Export to .env file for Docker Compose
cortex env export myapp > .env

# Docker Compose automatically loads .env
docker-compose up
```

### Systemd Services

Create a systemd environment file:

```bash
# Export to systemd environment file
cortex env export myapp > /etc/cortex/myapp.env
```

Then in your service file:
```ini
[Service]
EnvironmentFile=/etc/cortex/myapp.env
ExecStart=/usr/bin/myapp
```

## Encryption

### How It Works

Cortex uses Fernet encryption (symmetric encryption based on AES-128) to protect sensitive values:

- Encryption keys are generated using PBKDF2 with machine-specific data
- Keys are stored securely in `~/.cortex/.env_key` with 600 permissions
- Encrypted values are base64-encoded for safe storage
- Decryption happens automatically when retrieving values

### When to Encrypt

Encrypt variables containing:
- API keys and secrets
- Database credentials
- OAuth tokens
- Private keys
- Payment processor credentials

```bash
# Always encrypt sensitive data
cortex env set myapp OPENAI_API_KEY "sk-..." --encrypt
cortex env set myapp DATABASE_PASSWORD "secret" --encrypt
cortex env set myapp STRIPE_SECRET "sk_live_..." --encrypt
```

### Security Notes

- Encrypted values are marked as `[encrypted]` when listed or exported
- The encryption key is machine-specific and should not be shared
- For production, consider using a secrets management service
- Regular environment files (not encrypted) are still stored with 600 permissions

## Best Practices

### Organization

```bash
# Use descriptive names
cortex env set myapp DATABASE_URL "..."    # Good
cortex env set myapp DB "..."              # Avoid

# Add descriptions for team members
cortex env set myapp API_ENDPOINT "https://api.prod.com" \
  --description "Production API endpoint - do not modify"

# Use tags for filtering
cortex env set myapp FEATURE_FLAG "true" --tags feature production
```

### Security

```bash
# Always encrypt sensitive data
cortex env set myapp SECRET_KEY "..." --encrypt
cortex env set myapp API_KEY "..." --encrypt

# Regular backups
cortex env export myapp --format json > backups/myapp-$(date +%Y%m%d).json

# Use separate environments for different stages
cortex env set myapp-dev DATABASE_URL "postgres://localhost/dev"
cortex env set myapp-staging DATABASE_URL "postgres://staging/db"
cortex env set myapp-prod DATABASE_URL "postgres://prod/db" --encrypt
```

### Templates

```bash
# Create templates for your team's common setups
# This allows quick, consistent environment setup

# For new team members
cortex env template apply new-dev-setup nodejs \
  --var DATABASE_URL="postgres://localhost/dev" \
  --var NODE_ENV="development"

# Add custom variables after template
cortex env set new-dev-setup CUSTOM_VAR "custom_value"
```

### Version Control

```bash
# DO NOT commit encrypted values or .env files with secrets
# Instead, document required variables

# Create a template file
cat > myapp.env.template << EOF
# Required environment variables
DATABASE_URL=postgres://localhost/mydb
API_KEY=your_api_key_here
REDIS_URL=redis://localhost:6379
EOF

# Commit the template, not actual values
git add myapp.env.template
```

## Integration with Services

### Auto-load on Service Start

Create a wrapper script:

```bash
#!/bin/bash
# /usr/local/bin/start-myapp

# Load environment
eval "$(cortex env export myapp)"

# Start application
exec /usr/bin/myapp
```

### Python Service Integration

```python
# myapp/config.py
from cortex.env_manager import EnvManager
import os

class Config:
    def __init__(self, app_name="myapp"):
        # Load environment at startup
        manager = EnvManager()
        manager.load_env_to_os(app_name)
        
        # Access configuration
        self.DATABASE_URL = os.environ.get("DATABASE_URL")
        self.API_KEY = os.environ.get("API_KEY")
        self.DEBUG = os.environ.get("DEBUG", "False") == "True"

# Usage
config = Config()
```

### Node.js Service Integration

```javascript
// config.js
const { execSync } = require('child_process');

function loadEnv(appName) {
  const envOutput = execSync(`cortex env export ${appName}`).toString();
  envOutput.split('\n').forEach(line => {
    if (line.startsWith('export ')) {
      const [key, value] = line.slice(7).split('=');
      if (key && value) {
        process.env[key] = value.replace(/^"|"$/g, '');
      }
    }
  });
}

loadEnv('myapp');

module.exports = {
  databaseUrl: process.env.DATABASE_URL,
  apiKey: process.env.API_KEY,
};
```

## Troubleshooting

### Variable Not Found

```bash
# Check if app exists
cortex env list

# Check specific app
cortex env list myapp

# Verify variable name (case-sensitive)
cortex env get myapp DATABASE_URL
```

### Validation Errors

```bash
# Check validation rules
cortex env set myapp DATABASE_URL "invalid"
# Error: DATABASE_URL: Must be a valid URL

# Fix the value
cortex env set myapp DATABASE_URL "postgres://localhost/db"
```

### Encryption Issues

```bash
# If encryption key is lost, encrypted values cannot be recovered
# Always backup your environment:
cortex env export myapp > backup.env

# The encryption key is at:
ls -la ~/.cortex/.env_key
```

### Import Conflicts

```bash
# Use --merge to keep existing variables
cortex env import myapp new.env --merge

# Or replace all (default)
cortex env import myapp new.env
```

## API Reference

### Commands

| Command | Description |
|---------|-------------|
| `cortex env set <app> <key> <value>` | Set environment variable |
| `cortex env get <app> <key>` | Get environment variable |
| `cortex env list [app]` | List variables (or apps) |
| `cortex env delete <app> <key>` | Delete variable |
| `cortex env export <app>` | Export variables |
| `cortex env import <app> <file>` | Import variables |
| `cortex env template list` | List templates |
| `cortex env template apply <app> <template>` | Apply template |
| `cortex env clear <app>` | Clear all variables for app |

### Options

| Option | Description |
|--------|-------------|
| `--encrypt` | Encrypt the value |
| `--description <text>` | Add description |
| `--tags <tag1> <tag2>` | Add tags |
| `--format <format>` | Export/import format (env, json, yaml) |
| `--merge` | Merge on import instead of replace |
| `--var KEY=VALUE` | Template variable override |

## Storage Location

Environment variables are stored in:
```
~/.cortex/environments/         # Per-app environment files
~/.cortex/env_templates/        # Template definitions
~/.cortex/.env_key              # Encryption key (600 permissions)
```

All files are stored with restricted permissions (600) for security.

## Examples

### Django Application Setup

```bash
# Apply Django template
cortex env template apply mysite django \
  --var SECRET_KEY="$(openssl rand -base64 32)" \
  --var DATABASE_URL="postgres://localhost/mysite"

# Add custom settings
cortex env set mysite EMAIL_HOST "smtp.gmail.com"
cortex env set mysite EMAIL_PASSWORD "app-specific-password" --encrypt
cortex env set mysite ALLOWED_HOSTS "mysite.com,www.mysite.com"

# Export for deployment
cortex env export mysite > /etc/mysite/production.env
```

### Microservices Architecture

```bash
# API service
cortex env set api-service DATABASE_URL "postgres://db/api"
cortex env set api-service JWT_SECRET "..." --encrypt
cortex env set api-service PORT "3000"

# Worker service
cortex env set worker-service DATABASE_URL "postgres://db/api"
cortex env set worker-service REDIS_URL "redis://cache:6379"
cortex env set worker-service QUEUE_NAME "background-jobs"

# Frontend service
cortex env set frontend API_URL "http://api-service:3000"
cortex env set frontend NODE_ENV "production"
```

### Development to Production Workflow

```bash
# Development
cortex env template apply myapp nodejs \
  --var DATABASE_URL="postgres://localhost/dev" \
  --var NODE_ENV="development"

# Export development setup
cortex env export myapp > myapp-dev.env

# Production setup (separate app)
cortex env set myapp-prod DATABASE_URL "postgres://prod-db/myapp" --encrypt
cortex env set myapp-prod API_KEY "prod-api-key" --encrypt
cortex env set myapp-prod NODE_ENV "production"

# Export for deployment
cortex env export myapp-prod > /etc/myapp/production.env
```

## Contributing

To add new validation rules or templates, see [Contributing.md](../Contributing.md).

## Related Documentation

- [Configuration Management](CONFIGURATION.md)
- [Security](../SECURITY.md)
- [User Preferences](USER_PREFERENCES_IMPLEMENTATION.md)
