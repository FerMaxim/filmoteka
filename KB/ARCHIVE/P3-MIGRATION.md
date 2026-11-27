# T-009 · Матрица миграции P3

База `854c46e26bd292d79f43fd9b3d9b8a1ce0d5b96a`, main `d0e0d0be5a208153f81007f706b78ebfd1d9489c`. Сверка с SOURCE_MATERIALS, локальной копией T-005/KB, ветками проекта каталога и T-008. Решения владельца имеют приоритет. Подробный исходный текст доступен через `git show 854c46e:KB/<файл>`.

| Исходные ID или разделы | Статус | Назначение | Контроль сохранности |
|---|---|---|---|
| P01–P04, R02, R36/R47 | Утверждено | [PRODUCT](../PRODUCT.md), [CATALOG](../CATALOG.md) | Назначение сервиса, единый профиль, гость по ссылке, общий каталог; детали провайдера только в CATALOG |
| P05–P10, P14, U03–U09, R11–R15 | Утверждено, часть запланирована | [PRODUCT](../PRODUCT.md) | Добавление, планы, просмотр, избранное, оценка и рекомендация независимы; текст рекомендации необязателен; совместимость и совместный подбор отложены |
| P11/P11.1–P13, P16, U01–U02, R03–R10, R45, PRODUCT_SOURCE §3 | Утверждено | [PRODUCT](../PRODUCT.md) | Впечатление обязательно, семь критериев, 0–10 и шаг 0,1; фиксированные 50/50 только при заполненных дополнительных; ноль, пропуски, round half up; эмоции и комментарий отдельно; целое произведение, исключённые критерии |
| P15, D05–D06, R18/R33 | Утверждено с заменой | [DESIGN](../DESIGN.md), [PRODUCT](../PRODUCT.md) | Без статистики; один статичный фон, фото и сброс; без прочей персонализации, отдельная политика гостя |
| D01–D04, D07–D12, R16–R19, R32–R34 | Эталон утверждён; старые варианты исторические | [DESIGN](../DESIGN.md), [решения](../DECISIONS.md) | Режимы experimental/compact, v4, без Design Lab и переноса демоданных/лимитов; точное поведение по HTML; steins-gate.ru исторический |
| D13–D14, R21/R44 | Утверждено; приёмка ограничена T-003 | [DESIGN](../DESIGN.md), [ENGINEERING](../ENGINEERING.md) | Проектный навык, мобильная/широкая проверка и снимки; перенос с парными сравнениями, доступность, приёмка владельцем до merge |
| R35/R38/R40/R42, T-004/T-005 | Возможности интегрированы, историческая база сохранена | [PRODUCT](../PRODUCT.md), [ARCHITECTURE](../ARCHITECTURE.md), архив | Главная/логотип, сценарий 2а, auth_user/PK/права/сессии, необратимость AdoptUser, owner-only и повторяемость |
| R45, текущие границы доступа | Утверждено для 3/4; на main реализован приватный 2а | [PRODUCT](../PRODUCT.md), [ARCHITECTURE](../ARCHITECTURE.md) | Точный список полей гостя, изолированные личные данные, без самостоятельной регистрации; демо временное |
| R46, T-007 | Поведение утверждено; внешний вид открыт | [PRODUCT](../PRODUCT.md), [T-007](../TASKS/T-007.md) | Сохранение без перезагрузки, контекст/фокус, различимость, серверное состояние, вход/профиль/выход |
| R36/R37/R47, T-008 | Выбор, объём, TTL и fallback утверждены; реализация на ревью | [CATALOG](../CATALOG.md), [T-008](../TASKS/T-008.md) | Явный поиск, API v2.2, поля, один постер, локальные совпадения, общий кеш, ID, минимальные вызовы, TTL, бюджет, паузы, fallback и условия прав |
| CATALOG прежний проект и T-008 альтернативы | История и инженерные детали на ревью | [архив](README.md), [T-008](../TASKS/T-008.md) | Ранние v2.1, автопоиск, people/credits, расширенные поля исключены из выпуска; технические детали PR №9 остаются версионными |
| R22–R25, ARCHITECTURE модели, routes и фото | Стек утверждён; новые функции запланированы | [ARCHITECTURE](../ARCHITECTURE.md) | Модульный монолит, транзакции/версия/ограничения, разграничение доступа, HTTP и изолированная обработка будущих фотографий |
| R23/R26/R31/R39/R48, T-009 P2 | Действующие полномочия и процесс | [ENGINEERING](../ENGINEERING.md), [WORKFLOW](../WORKFLOW.md), [T-009](../TASKS/T-009.md) | Три независимые роли, резервирование, alias и SHA-проверки, review/CI на актуальном head, отдельное право merge, подтверждение P2 |
| R27–R30, ENGINEERING и LOCAL_DEVELOPMENT | Действуют нативные проверки | [ENGINEERING](../ENGINEERING.md), [LOCAL_DEVELOPMENT](../LOCAL_DEVELOPMENT.md) | Fail-closed CI, отчёт, одноразовые кластеры и проверка identity каждого соединения до SQL, миграции и сохранность dev-базы |
| R37/R41/R43, документы T-006 из соседней копии | Тестовая среда и исключение подтверждены; новый proxy проект | [OPERATIONS](../OPERATIONS.md), [решения](../DECISIONS.md), [T-006](../TASKS/T-006.md) | LXC/IP/TLS, без бэкапов лишь в T-006; точный SHA в BACKLOG, проверенный restart, открытые reboot/приёмка и данные proxy, независимые права выпуска |
| R01/R20, старый CURRENT_STATE и завершённые T-001–005 | Происхождение и доказательства | [решения](../DECISIONS.md), [архив](README.md), [BACKLOG](../BACKLOG.md) | Источник и полномочия каждого решения, исторические снимки, ID задач, SHA/PR/проверки; один реестр стадий |
| ROADMAP, AUDIT, исходные пакеты | Критерии этапов и история | [ROADMAP](../ROADMAP.md), [архив](README.md) | Критерии формулируются как условия завершения; исходники и визуальные артефакты сохраняются побайтно |

## Воспроизведение замеров

Как в P2, считать байты UTF-8 Git-блобов без преобразования переводов строк. Архив — AUDIT, HISTORY_* и ARCHIVE. Метрика активной КБ охватывает только Markdown внутри KB. Markdown внутри KB/ASSETS учитывается в активной метрике как в P2, даже когда используется лишь по ссылке. Размеры типовых контекстов — сумма полных обязательных файлов фиксированных примеров. Эталон, история, код и тесты открываются по задаче и в эти суммы не входят. Байты не измеряют расход токенов.

```powershell
$base = '854c46e26bd292d79f43fd9b3d9b8a1ce0d5b96a'
$entry = @('AGENTS.md', 'KB/README.md', 'KB/WORKFLOW.md', 'KB/BACKLOG.md')
$contexts = [ordered]@{
    Start = $entry
    UI = $entry + @('KB/PRODUCT.md', 'KB/DESIGN.md', 'KB/ENGINEERING.md',
                    'KB/TASKS/T-007.md', '.agents/skills/frontend-design/SKILL.md')
    Server = $entry + @('KB/PRODUCT.md', 'KB/ARCHITECTURE.md',
                        'KB/ENGINEERING.md', 'KB/TASKS/T-007.md')
    Catalog = $entry + @('KB/CATALOG.md', 'KB/ARCHITECTURE.md',
                         'KB/ENGINEERING.md', 'KB/TASKS/T-008.md')
}
foreach ($rev in @($base, (git rev-parse HEAD))) {
    $lines = git ls-tree -rl $rev -- KB | Where-Object { $_ -match '\.md$' }
    foreach ($kind in @('active', 'archive')) {
        $files = @($lines | Where-Object {
            ($_ -match 'KB/(?:(?:AUDIT|HISTORY_[^/]+)\.md$|ARCHIVE/)') -eq ($kind -eq 'archive')
        })
        $bytes = ($files | ForEach-Object { [int](($_ -split '\s+')[3]) } |
            Measure-Object -Sum).Sum
        "$rev ${kind}: $($files.Count) файлов, $bytes Б"
    }
    foreach ($kind in $contexts.Keys) {
        $files = $contexts[$kind]
        $bytes = ($files | ForEach-Object { [int](git cat-file -s "${rev}:$_") } |
            Measure-Object -Sum).Sum
        "$rev ${kind}: $($files.Count) файлов, $bytes Б"
    }
}
```
