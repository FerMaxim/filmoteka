import sys
from pathlib import Path
from wsgiref.simple_server import make_server

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application


def main(port_file):
    app = StaticFilesHandler(get_wsgi_application())
    with make_server("127.0.0.1", 0, app) as server:
        pending = port_file.with_suffix(".pending")
        pending.write_text(str(server.server_port), encoding="ascii")
        pending.replace(port_file)
        server.serve_forever()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
