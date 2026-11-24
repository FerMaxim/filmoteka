import json
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

opener = build_opener(ProxyHandler({}))
for route, status in [("ready", "ready"), ("live", "ok")]:
    deadline = time.monotonic() + 30
    while True:
        try:
            with opener.open(f"{sys.argv[1]}/health/{route}", timeout=3) as response:
                assert json.load(response) == {"status": status}
            break
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
