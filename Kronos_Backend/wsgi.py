"""
WSGI config for Kronos_Backend project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kronos_Backend.settings')

application = get_wsgi_application()
