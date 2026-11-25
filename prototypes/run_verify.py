import os
import subprocess
import sys
import time

os.environ.update(
    DJANGO_SECRET_KEY="prototype-local-only",
    DJANGO_ALLOWED_HOSTS="127.0.0.1",
    DJANGO_SETTINGS_MODULE="filmoteka.quick_settings",
)
server = subprocess.Popen(
    [
        sys.executable,
        "-u",
        "-c",
        "from django.core.wsgi import get_wsgi_application; from django.contrib.staticfiles.handlers import StaticFilesHandler; from wsgiref.simple_server import make_server; make_server('127.0.0.1',8025,StaticFilesHandler(get_wsgi_application())).serve_forever()",
    ],
)
try:
    time.sleep(2)
    subprocess.run([sys.executable, "prototypes/verify.py"], check=True, timeout=70)
finally:
    server.terminate()
