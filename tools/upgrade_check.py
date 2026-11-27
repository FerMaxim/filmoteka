"""Verify migration from the previous auth schema in a disposable cluster."""

import sys
from tools.check import run, test_env
from tools.native import temporary_workspace, postgres_cluster

with temporary_workspace() as folder, postgres_cluster(folder, test_env(), run) as env:
    legacy = env
    run([sys.executable, "-m", "tools.legacy_manage", "migrate", "--noinput"], legacy)
    run(
        [
            sys.executable,
            "-m",
            "tools.legacy_manage",
            "shell",
            "-c",
            """
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.backends.db import SessionStore
u = get_user_model().objects.create_user(username='legacy', password='synthetic-legacy-only')
v = get_user_model().objects.create_user(username='legacy-two', password='synthetic-legacy-only')
g = Group.objects.create(name='legacy-group')
u.groups.add(g)
u.user_permissions.add(Permission.objects.get(codename='change_user'))
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
Session.objects.create(session_key='legacy-session-key', session_data=SessionStore().encode({'proof': 'preserved', '_auth_user_id': str(u.pk), '_auth_user_backend': 'django.contrib.auth.backends.ModelBackend', '_auth_user_hash': u.get_session_auth_hash()}), expire_date=timezone.now() + timedelta(days=1))
""",
        ],
        legacy,
    )
    run([sys.executable, "manage.py", "migrate", "--noinput"], env)
    run(
        [
            sys.executable,
            "manage.py",
            "shell",
            "-c",
            """
from django.contrib.auth import get_user_model, authenticate
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
u = get_user_model().objects.get(username='legacy')
assert u.pk == 1 and u.check_password('synthetic-legacy-only')
assert authenticate(username='legacy', password='synthetic-legacy-only').pk == u.pk
assert u.groups.get().name == 'legacy-group'
assert u.has_perm('accounts.change_user')
assert SessionStore(session_key='legacy-session-key')['proof'] == 'preserved'
from django.test import Client
c = Client()
c.cookies['sessionid'] = 'legacy-session-key'
assert c.get('/me/library/').status_code == 200
assert len(set(get_user_model().objects.values_list('public_id', flat=True))) == 2
assert get_user_model().objects.create_user(username='after-upgrade').pk > 2
with connection.cursor() as c:
    c.execute("SELECT data_type FROM information_schema.columns WHERE table_name='auth_user' AND column_name='id'")
    assert c.fetchone()[0] == 'bigint'
print('Legacy upgrade: users, passwords, permissions, groups, sessions and sequence preserved')
""",
        ],
        env,
    )
