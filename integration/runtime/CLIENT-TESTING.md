# Клиентские испытания и подтверждение результатов

Инструкция применима к OpenCode, DeepSeek Harness, Claude Code, Codex и Cursor. Проверка должна проходить в **изолированном искусственном проекте**, не на рабочем или приватном коде. Клиентские вызовы могут использовать сеть и платную модель; требуется отдельная команда человека.

## 1. Подготовка

```sh
python integration/runtime/real_client.py probe
mkdir disposable-workspace
python integration/runtime/real_client.py prepare --platform codex --workspace ./disposable-workspace --fixture skill-clean
python integration/runtime/cli_e2e.py plan --workspace ./disposable-workspace
```

Параметр `--platform` меняется в зависимости от клиента. Перед реальным испытанием установи и авторизуй клиент самостоятельно, проверь `--help` и реальные права доступа, версию CLI и модель. Не передавай модели эталоны из `quality/gold/`.

## 2. Ограниченное испытание CLI

На машине с настроенным клиентом, **только после проверки ограничительного режима и явного разрешения**:

```sh
python integration/runtime/cli_e2e.py run --workspace ./disposable-workspace --execute --consent --timeout 180
```

`plan` не вызывает модель. `run` без обоих флагов согласия не должен запускать клиента. Пробный запрос проверяет обнаружение и чтение инструкций, **не весь конвейер AUDIT → DOCS**. Не включай обход разрешений (`--force`, `--full-auto`, `--dangerously-skip-permissions`). Даже read-only флаги CLI не являются гарантией изоляции ОС: для строгих проверок используй отдельную VM/контейнер и ограничения сети.

| Клиент | Условие ограниченного запуска |
|---|---|
| OpenCode | Проверенная действующая схема `permissions`/`policies`; проектную конфигурацию нельзя самовольно перезаписывать |
| DeepSeek Harness | `dsh --profile headless` **не подтверждает read-only**; автоматический прогон блокируется `BLOCKED_READ_ONLY_UNVERIFIED` |
| Claude Code | Проверенный режим без записи и штатные разрешения клиента |
| Codex | Sandbox `read-only` для теста обнаружения, отдельный разрешённый режим для публикации |
| Cursor | Для первого теста проверенный Ask mode; не используй `agent -p` без ограничений |

Не предполагай неизменность CLI между релизами: проверь параметры с установленной версией. Запуск без защитного режима не допускается по умолчанию.

## 3. Проверка фактической активации и безопасности

Проверь раздельно: обнаружение Skill; загрузку `audit-workflow/SKILL.md` и `references/preflight.md`; переходы между профилем аудита, улучшениями, модернизацией и документацией; итоговые файлы `audit/README.md`, `audit/docs/`, `audit/translations/`; неизменность `subject/`; отсутствие автоматической генерации.

Запиши версию клиента/модели, фактические действия, исходные журналы и их SHA-256. Сохраняй логи внутри `.integration-test/` в тестовом workspace, проверяя отсутствие секретов и персональных данных. `run_id`, пути и имена файлов должны соответствовать исходному проекту. `PASS` в `.integration-test/evidence.json` — **заявление оператора**, не автоматическая сертификация.

```sh
python integration/runtime/cli_e2e.py verify --workspace ./disposable-workspace
python integration/runtime/real_client.py assess --workspace ./disposable-workspace
python integration/runtime/compatibility_report.py --workspace ./disposable-workspace
```

Повторяй `--workspace` для нескольких проектов. Допустим `--no-probe` для отказа даже от поиска бинарников. `INVALID_EVIDENCE` означает повреждение/несоответствие; `REVIEW_REQUIRED` — требуется независимый просмотр реальных журналов. Локальные SHA-256 не доказывают происхождение файлов. `CLIENT_PASS` разрешён только после проверки реальной сессии независимым рецензентом.

## 4. Полноценный аудит и оценка качества

Тест обнаружения с коротким запросом **не подходит для расчёта Precision/Recall/F1**. Для оценки аудита отдельно запускай все 12 тестовых случаев из `quality/fixtures/` в независимых проектах. Не показывай клиенту `quality/gold/` и `quality/examples/predictions-perfect.json` до получения ответов. Результат каждого случая сохрани в `.integration-test/predictions.json`:

```json
{"case_id":"skill-clean", "findings":[], "recommendations":[]}
```

После сбора результатов подготовленных проектов:

```sh
python integration/runtime/quality_bridge.py --workspace ./audit-test-01 --workspace ./audit-test-02
```

При неполном наборе статус `INCOMPLETE`, метрик нет. После сбора всех 12 проектов передай все их `--workspace` и добавь `--score`. Эталонные ответы применяются **после** получения независимых предсказаний. Метрики относятся только к синтетическому набору и не удостоверяют происхождение LLM-ответов или качество переводов по смыслу.

## 5. Передача результатов

```sh
python integration/runtime/evidence_export.py --workspace ./disposable-workspace --output ./client-evidence.zip
```

По умолчанию экспортируется только обезличенная сводка; логи могут содержать конфиденциальные данные и требуют отдельного разрешения и проверки архива перед отправкой. Пакет свидетельств также не является доказательством подлинности без независимого просмотра сеанса.

## 6. Итоговые статусы

- `LOCAL_INSTALL_PASS` / `CLI_PRESENT` — проверено наличие файлов или кандидата бинарника, а не работа Skill.
- `NOT_TESTED` — отсутствует реальный запуск или проверяемое наблюдение.
- `BLOCKED_READ_ONLY_UNVERIFIED` — режим безопасности клиента не подтверждён.
- `REVIEW_REQUIRED` — журналы есть, но достоверность и полнота не подтверждены независимо.
- `INVALID_EVIDENCE` — контрольные данные некорректны или изменены.
- `CLIENT_PASS` — только независимый итог реального испытания с подробным основанием.

## Документация команд

- [OpenCode CLI](https://opencode.ai/docs/cli/commands)
- [OpenCode permissions](https://opencode.ai/docs/permissions/)
- [DeepSeek Harness CLI](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/README.md)
- [Claude Code CLI](https://code.claude.com/docs/en/headless)
- [Codex CLI](https://learn.chatgpt.com/docs/cli/reference)
- [Cursor CLI](https://cursor.com/docs/cli/using)
