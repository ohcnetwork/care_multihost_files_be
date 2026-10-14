from django.apps import AppConfig

PLUGIN_NAME = "care_multihost_files_be"


class CareMultihostFilesConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = "CARE multihost files"

    def ready(self):
        from care_multihost_files_be import multihost

        multihost.setup()
