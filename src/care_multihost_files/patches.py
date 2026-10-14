import functools
import importlib
import logging

from django.apps import apps

from care_multihost_files.host import rehost

logger = logging.getLogger(__name__)

CONFIG_MODULE = "care.utils.csp.config"
CONFIG_FUNCTIONS = ("get_facility_bucket_config", "get_patient_bucket_config", "get_report_bucket_config")
URL_METHODS = (("facility", "Facility", "read_cover_image_url"), ("users", "User", "read_profile_picture_url"))

_MARK = "__care_multihost_files__"


def _wrap_config(original):
    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        params, bucket = original(*args, **kwargs)
        external = kwargs.get("external", args[0] if args else False)
        if external and params.get("endpoint_url"):
            params = {**params, "endpoint_url": rehost(params["endpoint_url"])}
        return params, bucket

    setattr(wrapper, _MARK, True)
    return wrapper


def _wrap_url(original):
    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        return rehost(original(self, *args, **kwargs))

    setattr(wrapper, _MARK, True)
    return wrapper


def _patch(owner, name, wrap) -> bool:
    original = getattr(owner, name, None)
    if original is None:
        logger.warning("care_multihost_files: %s.%s not found; file links there keep their usual address", owner, name)
        return False
    if not getattr(original, _MARK, False):
        setattr(owner, name, wrap(original))
    return True


def install() -> list[str]:
    patched = []
    try:
        module = importlib.import_module(CONFIG_MODULE)
    except ImportError:
        logger.warning("care_multihost_files: %s not found; signed file links keep their usual address", CONFIG_MODULE)
    else:
        for name in CONFIG_FUNCTIONS:
            if _patch(module, name, _wrap_config):
                patched.append(f"{CONFIG_MODULE}.{name}")
    for app_label, model_name, method in URL_METHODS:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            logger.warning("care_multihost_files: model %s.%s not found", app_label, model_name)
            continue
        if _patch(model, method, _wrap_url):
            patched.append(f"{app_label}.{model_name}.{method}")
    return patched
