import unittest

from django.core.signals import request_finished, request_started
from django.test import override_settings

from care_multihost_files import host
from care_multihost_files.settings import _patterns, allowed_hosts


class SettingsTests(unittest.TestCase):
    def test_patterns_accept_lists_json_and_commas(self):
        self.assertEqual(_patterns(["*.Local", " *.ts.net "]), ["*.local", "*.ts.net"])
        self.assertEqual(_patterns('["*.local","*.ts.net"]'), ["*.local", "*.ts.net"])
        self.assertEqual(_patterns("*.local, *.ts.net,"), ["*.local", "*.ts.net"])
        self.assertEqual(_patterns(None), [])
        self.assertEqual(_patterns("[not json"), [])

    def test_missing_plugin_config_allows_nothing(self):
        with override_settings(PLUGIN_CONFIGS={}):
            self.assertEqual(allowed_hosts(), [])


class HostTests(unittest.TestCase):
    def setUp(self):
        host.connect()
        self.addCleanup(host.use, None)

    def test_is_allowed_ignores_port_and_case(self):
        self.assertTrue(host.is_allowed("care.local"))
        self.assertTrue(host.is_allowed("Clinic.Tail1234.TS.NET:8443"))
        self.assertFalse(host.is_allowed("evil.example.com"))
        self.assertFalse(host.is_allowed(""))

    def test_request_started_remembers_only_allowed_hosts(self):
        request_started.send(sender=None, environ={"HTTP_HOST": "clinic.tail1234.ts.net:8443"})
        self.assertEqual(host.current(), "clinic.tail1234.ts.net:8443")
        request_finished.send(sender=None)
        self.assertIsNone(host.current())
        request_started.send(sender=None, environ={"HTTP_HOST": "evil.example.com"})
        self.assertIsNone(host.current())

    def test_forwarded_host_wins(self):
        request_started.send(
            sender=None, environ={"HTTP_HOST": "caddy", "HTTP_X_FORWARDED_HOST": "care.local, other.local"}
        )
        self.assertEqual(host.current(), "care.local")

    def test_asgi_scope(self):
        request_started.send(sender=None, scope={"headers": [(b"host", b"clinic.tail1234.ts.net:8443")]})
        self.assertEqual(host.current(), "clinic.tail1234.ts.net:8443")

    def test_rehost_only_rewrites_storage_behind_allowed_hosts(self):
        signed = "https://care.local/patient-bucket/PATIENT/a.pdf?X-Amz-Signature=abc"
        self.assertEqual(host.rehost(signed), signed)
        host.use("clinic.tail1234.ts.net:8443")
        self.assertEqual(
            host.rehost(signed),
            "https://clinic.tail1234.ts.net:8443/patient-bucket/PATIENT/a.pdf?X-Amz-Signature=abc",
        )
        s3 = "https://bucket.s3.amazonaws.com/PATIENT/a.pdf"
        self.assertEqual(host.rehost(s3), s3)
        self.assertIsNone(host.rehost(None))
        self.assertEqual(host.rehost("/relative/path"), "/relative/path")


if __name__ == "__main__":
    unittest.main()
