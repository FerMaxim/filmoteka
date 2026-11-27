#!/bin/sh
# T-006: additive preparation for the inventoried Ubuntu 22.04 LXC.
# Run as root only after inventory; no application release is deployed.
set -eu
test "$(id -u)" = 0
if ! getent passwd filmoteka >/dev/null; then
    useradd --system --home-dir /srv/filmoteka --shell /usr/sbin/nologin filmoteka
fi
install -d -o root -g filmoteka -m 0750 /etc/filmoteka /srv/filmoteka
install -d -o root -g filmoteka -m 0750 /srv/filmoteka/releases /srv/filmoteka/shared
chmod 0751 /srv/filmoteka /srv/filmoteka/shared
install -d -o filmoteka -g filmoteka -m 0750 /srv/filmoteka/shared/media
install -d -o root -g www-data -m 0750 /srv/filmoteka/shared/static
install -d -o root -g root -m 0755 /opt/filmoteka /opt/filmoteka/python

# Official PostgreSQL repository with a dedicated signing key.
install -d -m 0755 /usr/share/postgresql-common/pgdg
curl --fail --silent --show-error --location --max-time 60 \
    https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
cat > /etc/apt/sources.list.d/pgdg.sources <<'EOF'
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: jammy-pgdg
Architectures: amd64
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-17

# Download the official installer to a file; failures cannot become partial shell input.
curl --fail --silent --show-error --location --max-time 60 \
    https://astral.sh/uv/0.13.10/install.sh -o /opt/filmoteka/uv-install.sh
UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR=/usr/local/bin sh /opt/filmoteka/uv-install.sh
UV_PYTHON_INSTALL_DIR=/opt/filmoteka/python /usr/local/bin/uv python install 3.13.18
chmod -R a+rX /opt/filmoteka/python
/usr/local/bin/uv --version
UV_PYTHON_INSTALL_DIR=/opt/filmoteka/python /usr/local/bin/uv python find 3.13
