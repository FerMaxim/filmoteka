# Локальная разработка из PowerShell

## Установка

Установите uv и PostgreSQL 17 для Windows со службой и командными инструментами. Запомните локальный порт и пароль администратора для создания dev-базы. [Установка uv](https://docs.astral.sh/uv/getting-started/installation/) · [Загрузки PostgreSQL для Windows](https://www.postgresql.org/download/windows/)

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


## Приватная библиотека и диагностика

После migrate выполнить `uv run python manage.py seed_synthetic`. Команда повторяема, готовит три произведения без API и аккаунтов. Локального пользователя создаёт владелец среды через Django shell и `get_user_model().objects.create_user` с паролем из `getpass.getpass()`. Вход через `/accounts/login/`, каталог `/catalog/`, библиотека `/me/library/`.

- PostgreSQL не найден — проверить `PG_BIN` или PATH и версии `postgres`, `initdb`, `pg_ctl`.
- Live успешен, ready нет — проверить службу PostgreSQL, адрес, порт, роль и БД в локальной конфигурации. Dev и тесты имеют разные координаты.
- Старую схему отдельно проверяет `uv run --locked --no-sync python -m tools.upgrade_check`. Full проверяет старую и чистую схемы на разных кластерах.
- Ошибка запуска браузера — проверить установленный Chromium Playwright и доступ к loopback. Full/browser создают тестового пользователя и проверяют сессию и библиотеку после restart. Cookie остаётся во временной папке; снимки в `test-results/T-005` или `FILMOTEKA_SCREENSHOTS`.
- Прямой `tools.browser` требует test settings, тестовый backend и маркер кластера. Для проверки отдельных гостевых переходов предусмотрен `prototypes/home_verify.py`. При ограничениях Windows направить TEMP/TMP в разрешённый временный каталог и обеспечить доступ к loopback.

## Проверка интеграции каталога T-008

`python tools/check.py target tests/test_kinopoisk.py` использует fixtures и отдельный кластер PostgreSQL. `full` проверяет миграцию прежней схемы, HTTP, Playwright и restart со снятым разрешением. Снимки создаются в `test-results/T-008`. Диспетчер исключает наследуемые `KINOPOISK_*`, а браузер локально перехватывает обращения к постерам.

В локальной среде флаги из `.env.example` по умолчанию равны 0. Условия живого режима приведены в [CATALOG](CATALOG.md#допуск-живого-режима).
