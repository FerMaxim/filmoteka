# Локальная разработка из PowerShell

## Установка

Установите `uv` по инструкции Astral и PostgreSQL 17 для Windows с сервером и командными инструментами. Установщик PostgreSQL предлагает создать службу. Выберите локальный порт и задайте пароль администратора базы, он понадобится только при её создании. Python 3.13 можно установить через `uv`. [Установка uv](https://docs.astral.sh/uv/getting-started/installation/) · [Загрузки PostgreSQL для Windows](https://www.postgresql.org/download/windows/)

Откройте новое окно PowerShell и перейдите в корень репозитория. `PG_BIN` указывает на каталог установки PostgreSQL с `postgres.exe`, `initdb.exe` и `pg_ctl.exe`. Подставьте свой путь, если меняли его в установщике.

```powershell
uv python install 3.13
uv sync --locked --python 3.13
$env:PG_BIN = 'C:\Program Files\PostgreSQL\17\bin'
& "$env:PG_BIN\postgres.exe" --version
```

## Постоянная база разработки

Один раз создайте отдельную локальную роль и базу. Если выбрали другой порт установки, замените `5432` здесь и укажите его в `.env`.

```powershell
& "$env:PG_BIN\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

Проверьте `SHOW listen_addresses;` в `psql`. Для локальной работы допустимы `localhost` и адреса loopback. Если сервер слушает другие интерфейсы, задайте `listen_addresses = 'localhost'` в `postgresql.conf` и перезапустите свою службу PostgreSQL. Затем в приглашении `psql` выполните команды создания базы. `\password` запросит пароль роли разработки.

```sql
CREATE ROLE filmoteka LOGIN;
\password filmoteka
CREATE DATABASE filmoteka OWNER filmoteka;
\q
```

Создайте локальный `.env` из шаблона. Сохраните выведенный ключ в `DJANGO_SECRET_KEY` и пароль роли разработки в `POSTGRES_PASSWORD`. Пароли со знаками, которые в dotenv имеют особый смысл, заключайте в одинарные кавычки. `.env` исключён из Git.

```powershell
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item .env.example .env }
uv run --locked --no-sync python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Запуск

```powershell
uv run --locked --no-sync --env-file .env python manage.py migrate --noinput
uv run --locked --no-sync --env-file .env python manage.py runserver 127.0.0.1:8000 --noreload
```

Проверьте из второго окна PowerShell. Первая команда возвращает `ok`, вторая — `ready`.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Остановите Django через Ctrl+C в его окне. Следующий запуск использует ту же базу из `.env`. При проверке сохранности прочитайте ранее созданную контрольную запись после перезапуска Django и службы PostgreSQL.

## Проверки

Запускайте команды из корня репозитория. `quick` использует Python-зависимости. `target`, `smoke`, `browser` и `full` требуют PostgreSQL 17 на `PATH` или в `PG_BIN` и создают отдельный временный кластер. Установите Chromium Playwright перед первым `browser` или `full` и после обновления версии Playwright.

```powershell
uv run --locked --no-sync python tools/check.py docs
uv run --locked --no-sync python tools/check.py quick
uv run --locked --no-sync python tools/check.py target tests/test_database.py
uv run --locked --no-sync python -m playwright install --only-shell chromium
uv run --locked --no-sync python tools/check.py full
```
