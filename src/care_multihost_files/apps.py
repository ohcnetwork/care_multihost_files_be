from django.apps import AppConfig

PLUGIN_NAME = "care_multihost_files"


class CareMultihostFilesConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = "CARE multihost files"

    def ready(self):
        from care_multihost_files import multihost

        multihost.setup()
