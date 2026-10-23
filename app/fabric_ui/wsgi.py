"""WSGI entry point, served by gunicorn in the container."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabric_ui.settings")

application = get_wsgi_application()
