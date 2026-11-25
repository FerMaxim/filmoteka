import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

os.environ.update(
    DJANGO_SECRET_KEY="prototype-local-only",
    DJANGO_ALLOWED_HOSTS="127.0.0.1",
    DJANGO_SETTINGS_MODULE="filmoteka.quick_settings",
)
with TemporaryDirectory(prefix="prototype-") as folder:
    port_file = Path(folder) / "port"
    server = subprocess.Popen([sys.executable, "-m", "tools.test_web", str(port_file)])
    try:
        deadline = time.monotonic() + 20
        while not port_file.exists():
            if server.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Prototype server failed to become ready")
            time.sleep(0.1)
        os.environ["PROTOTYPE_URL"] = "http://127.0.0.1:" + port_file.read_text()
        subprocess.run(
            [sys.executable, "prototypes/verify.py"], check=True, timeout=240
        )
        subprocess.run(
            [sys.executable, "prototypes/accessibility.py"], check=True, timeout=240
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
