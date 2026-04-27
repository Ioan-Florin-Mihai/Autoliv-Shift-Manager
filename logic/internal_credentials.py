"""Internal credential bootstrap constants.

This module no longer ships a predictable admin password. It only defines the
bootstrap username and password-generation policy used by ``logic.auth`` when
``users.json`` must be created locally on first run.
"""

DEFAULT_ADMIN_USERNAME = "admin"
BOOTSTRAP_PASSWORD_LENGTH = 18
