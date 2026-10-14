import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[],
        PLUGIN_CONFIGS={"care_multihost_files": {"ALLOWED_HOSTS": ["*.local", "*.ts.net"]}},
    )
    django.setup()
