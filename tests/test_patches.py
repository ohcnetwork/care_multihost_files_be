import sys
import types
import unittest

from care_multihost_files import host, patches


def _fake_config_module():
    module = types.ModuleType(patches.CONFIG_MODULE)

    def make(endpoint_external, endpoint_internal, bucket):
        def config(external):
            return {"endpoint_url": endpoint_external if external else endpoint_internal}, bucket

        return config

    module.get_facility_bucket_config = make("https://care.local", "http://minio:9000", "facility-bucket")
    module.get_patient_bucket_config = make("https://care.local", "http://minio:9000", "patient-bucket")
    module.get_report_bucket_config = make("https://care.local", "http://minio:9000", "patient-bucket")

    def get_client_config(bucket_type, external=False):
        return module.get_patient_bucket_config(external=external)

    module.get_client_config = get_client_config
    return module


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.module = _fake_config_module()
        parents = ("care", "care.utils", "care.utils.csp")
        self.saved = {name: sys.modules.get(name) for name in (*parents, patches.CONFIG_MODULE)}
        for name in parents:
            sys.modules[name] = types.ModuleType(name)
        sys.modules[patches.CONFIG_MODULE] = self.module
        self.addCleanup(self._restore)
        self.addCleanup(host.use, None)

    def _restore(self):
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_install_wraps_config_functions_once(self):
        patched = patches.install()
        self.assertEqual(len([name for name in patched if name.startswith(patches.CONFIG_MODULE)]), 3)
        first = self.module.get_patient_bucket_config
        patches.install()
        self.assertIs(self.module.get_patient_bucket_config, first)

    def test_external_endpoint_follows_request_host(self):
        patches.install()
        host.use("clinic.tail1234.ts.net:8443")
        params, bucket = self.module.get_client_config("PATIENT", external=True)
        self.assertEqual(params["endpoint_url"], "https://clinic.tail1234.ts.net:8443")
        self.assertEqual(bucket, "patient-bucket")
        params, _ = self.module.get_client_config("PATIENT")
        self.assertEqual(params["endpoint_url"], "http://minio:9000")

    def test_without_request_nothing_changes(self):
        patches.install()
        params, _ = self.module.get_patient_bucket_config(True)
        self.assertEqual(params["endpoint_url"], "https://care.local")

    def test_url_methods_are_rehosted(self):
        class Facility:
            def read_cover_image_url(self):
                return "https://care.local/facility-bucket/cover.png"

        patches._patch(Facility, "read_cover_image_url", patches._wrap_url)
        host.use("clinic.tail1234.ts.net:8443")
        self.assertEqual(
            Facility().read_cover_image_url(), "https://clinic.tail1234.ts.net:8443/facility-bucket/cover.png"
        )

    def test_missing_targets_are_skipped(self):
        class Empty:
            pass

        self.assertFalse(patches._patch(Empty, "read_cover_image_url", patches._wrap_url))


if __name__ == "__main__":
    unittest.main()
