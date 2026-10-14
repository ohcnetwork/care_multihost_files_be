from contextvars import ContextVar
from fnmatch import fnmatchcase
from urllib.parse import urlsplit, urlunsplit

from django.core.signals import request_finished, request_started

from care_multihost_files.settings import allowed_hosts

_current: ContextVar[str | None] = ContextVar("care_multihost_files_host", default=None)


def _hostname(netloc: str) -> str:
    netloc = netloc.strip().lower()
    if netloc.startswith("["):
        return netloc.split("]", 1)[0] + "]"
    return netloc.rsplit(":", 1)[0] if netloc.count(":") == 1 else netloc


def is_allowed(netloc: str) -> bool:
    name = _hostname(netloc)
    if not name:
        return False
    return any(fnmatchcase(name, pattern) for pattern in allowed_hosts())


def _first(value: str | None) -> str:
    return (value or "").split(",", 1)[0].strip()


def host_from_environ(environ: dict) -> str:
    return _first(environ.get("HTTP_X_FORWARDED_HOST")) or _first(environ.get("HTTP_HOST"))


def host_from_scope(scope: dict) -> str:
    headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers") or []}
    return _first(headers.get("x-forwarded-host")) or _first(headers.get("host"))


def _started(sender, environ=None, scope=None, **kwargs):
    if environ is not None:
        netloc = host_from_environ(environ)
    elif scope is not None:
        netloc = host_from_scope(scope)
    else:
        netloc = ""
    _current.set(netloc.lower() if netloc and is_allowed(netloc) else None)


def _finished(sender, **kwargs):
    _current.set(None)


def connect():
    request_started.connect(_started, dispatch_uid="care_multihost_files_started")
    request_finished.connect(_finished, dispatch_uid="care_multihost_files_finished")


def current() -> str | None:
    return _current.get()


def use(netloc: str | None):
    return _current.set(netloc)


def rehost(url: str | None) -> str | None:
    netloc = current()
    if not url or not netloc:
        return url
    parts = urlsplit(url)
    if not parts.netloc or parts.netloc.lower() == netloc or not is_allowed(parts.netloc):
        return url
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
