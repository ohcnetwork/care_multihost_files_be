import json
import os

from django.conf import settings

from care_multihost_files.apps import PLUGIN_NAME

ALLOWED_HOSTS = "ALLOWED_HOSTS"
ENV_ALLOWED_HOSTS = "MULTIHOST_FILES_ALLOWED_HOSTS"


def _patterns(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                return _patterns(json.loads(text))
            except json.JSONDecodeError:
                return []
        return [part.strip().lower() for part in text.split(",") if part.strip()]
    if isinstance(value, list | tuple):
        return [str(part).strip().lower() for part in value if str(part).strip()]
    return []


def allowed_hosts() -> list[str]:
    configs = getattr(settings, "PLUGIN_CONFIGS", {}) or {}
    plugin = configs.get(PLUGIN_NAME) or {}
    if ALLOWED_HOSTS in plugin:
        return _patterns(plugin[ALLOWED_HOSTS])
    return _patterns(os.environ.get(ENV_ALLOWED_HOSTS))
