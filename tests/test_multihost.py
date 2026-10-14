import unittest

from django.core.signals import request_finished, request_started

from care_multihost_files import multihost

SIGNED = "https://care.local/patient-bucket/PATIENT/a.pdf?X-Amz-Signature=abc"
HOME = "clinic.tail1234.ts.net:8443"


class MultihostTests(unittest.TestCase):
    def setUp(self):
        request_started.connect(multihost.started, dispatch_uid="care_multihost_files_started")
        request_finished.connect(multihost.finished, dispatch_uid="care_multihost_files_finished")
        self.addCleanup(request_finished.send, sender=None)

    def test_allowed_ignores_port_and_case(self):
        self.assertTrue(multihost.allowed("care.local"))
        self.assertTrue(multihost.allowed("Clinic.Tail1234.TS.NET:8443"))
        self.assertFalse(multihost.allowed("evil.example.com"))

    def test_started_remembers_only_allowed_hosts(self):
        request_started.send(sender=None, environ={"HTTP_HOST": HOME})
        self.assertEqual(multihost.rehost(SIGNED), f"https://{HOME}/patient-bucket/PATIENT/a.pdf?X-Amz-Signature=abc")
        request_finished.send(sender=None)
        self.assertEqual(multihost.rehost(SIGNED), SIGNED)
        request_started.send(sender=None, environ={"HTTP_HOST": "evil.example.com"})
        self.assertEqual(multihost.rehost(SIGNED), SIGNED)

    def test_wrap_config_changes_only_external_endpoints(self):
        def config(external):
            return {"endpoint_url": "https://care.local" if external else "http://minio:9000"}, "patient-bucket"

        wrapped = multihost.wrap_config(config)
        request_started.send(sender=None, environ={"HTTP_HOST": HOME})
        self.assertEqual(wrapped(external=True), ({"endpoint_url": f"https://{HOME}"}, "patient-bucket"))
        self.assertEqual(wrapped(external=False), ({"endpoint_url": "http://minio:9000"}, "patient-bucket"))

    def test_wrap_url(self):
        class Facility:
            def read_cover_image_url(self):
                return "https://care.local/facility-bucket/cover.png"

        Facility.read_cover_image_url = multihost.wrap_url(Facility.read_cover_image_url)
        self.assertEqual(Facility().read_cover_image_url(), "https://care.local/facility-bucket/cover.png")
        request_started.send(sender=None, environ={"HTTP_HOST": HOME})
        self.assertEqual(Facility().read_cover_image_url(), f"https://{HOME}/facility-bucket/cover.png")


if __name__ == "__main__":
    unittest.main()
