import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# This smoke test does not contact PostgreSQL or Gemini. It verifies the
# production configuration rules and local auth fallback used by development.

os.environ["TCA_ENV"] = "production"
os.environ["TCA_AUTH_SECRET"] = "x" * 48
os.environ["TCA_CLOUD_ENABLED"] = "true"
os.environ["TCA_CLOUD_REQUIRED"] = "true"
os.environ["DATABASE_URL"] = "postgresql://example.invalid/tca"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["TCA_FRONTEND_URLS"] = "https://example.netlify.app"
os.environ["TCA_ALLOWED_HOSTS"] = "example.onrender.com"

from backend.app.config import get_config, validate_startup

config = validate_startup()
assert config.production
assert config.cloud_required
assert config.database_url
assert config.gemini_api_key
assert config.frontend_origins == ("https://example.netlify.app",)

# Development mode must still work without production secrets.
get_config.cache_clear()
os.environ["TCA_ENV"] = "development"
os.environ.pop("DATABASE_URL", None)
os.environ["TCA_CLOUD_ENABLED"] = "false"
os.environ["TCA_CLOUD_REQUIRED"] = "false"
os.environ.pop("GEMINI_API_KEY", None)

config = validate_startup()
assert not config.production
assert not config.cloud_enabled

print("Production configuration smoke test passed.")
