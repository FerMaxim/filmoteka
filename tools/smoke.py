import json
import time
from urllib.error import URLError
from urllib.request import urlopen

for route, status in [("ready", "ready"), ("live", "ok")]:
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen(f"http://web:8000/health/{route}", timeout=3) as response:
                assert json.load(response) == {"status": status}
            break
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
