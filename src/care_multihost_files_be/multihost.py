from contextvars import ContextVar
from fnmatch import fnmatchcase
from urllib.parse import urlsplit

from django.apps import apps
from django.conf import settings
from django.core.signals import request_finished, request_started

from care_multihost_files_be.apps import PLUGIN_NAME

_host = ContextVar("care_multihost_files_be_host", default=None)


def allowed(host):
    patterns = settings.PLUGIN_CONFIGS.get(PLUGIN_NAME, {}).get("ALLOWED_HOSTS", [])
    name = host.split(":")[0].lower()
    return any(fnmatchcase(name, pattern.lower()) for pattern in patterns)


def started(sender, environ, **kwargs):
    host = environ.get("HTTP_HOST", "").lower()
    _host.set(host if host and allowed(host) else None)


def finished(sender, **kwargs):
    _host.set(None)


def rehost(url):
    host = _host.get()
    if not url or not host:
        return url
    return urlsplit(url)._replace(netloc=host).geturl()


def wrap_config(original):
    def wrapper(external):
        params, bucket = original(external)
        if external and params.get("endpoint_url"):
            params["endpoint_url"] = rehost(params["endpoint_url"])
        return params, bucket

    return wrapper


def wrap_url(original):
    def wrapper(self):
        return rehost(original(self))

    return wrapper


def setup():
    request_started.connect(started, dispatch_uid="care_multihost_files_be_started")
    request_finished.connect(finished, dispatch_uid="care_multihost_files_be_finished")

    from care.utils.csp import config

    for name in ("get_facility_bucket_config", "get_patient_bucket_config", "get_report_bucket_config"):
        setattr(config, name, wrap_config(getattr(config, name)))

    for model, method in (("facility.Facility", "read_cover_image_url"), ("users.User", "read_profile_picture_url")):
        cls = apps.get_model(model)
        setattr(cls, method, wrap_url(getattr(cls, method)))
