"""
Import all models here so their tables are registered on Base.metadata.

This module is the single place that "knows about" every model.
It is imported only by:
  - alembic/env.py  (so Alembic can detect schema changes)
  - app/main.py     (so the app has the full metadata on startup)

No model module should ever import from this file.
"""

from app.models.user import User  # noqa: F401
from app.models.otp import OTP    # noqa: F401

# Add future models here, e.g.:
# from app.models.profile import Profile  # noqa: F401