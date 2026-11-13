# workflow_state.py — локальный менеджер этапов

> Не является AI-агентом и не исполняет аудируемые файлы. Python 3.10+; зависимости `jsonschema` и `markdown-it-py` устанавливаются пользователем вручную из `requirements.txt`. Для самих Skills Python не обязателен.

Схемы: [stage-result.schema.json](../schemas/stage-result.schema.json), [manifest.schema.json](../schemas/manifest.schema.json); пример: [AUDIT.example.json](../examples/AUDIT.example.json).

## 1. Создание нового запуска

```shell
python /path/to/audit-workflow/scripts/workflow_state.py init \
  --target /path/to/candidate \
  --type skill \
  --report-dir /path/to/candidate/audit
```

Здесь `/path/to/audit-workflow` — **каталог установленного скилла**, а не исследуемого инструмента. Подставь реальные пути, явно выбранные человеком.

После `init` в `<report-dir>/state/manifest.json` сохранён `run_id`; подставляй его в JSON-результаты всех этапов. `init` откажется изменять существующий запуск. Для нового запуска выбирай новый пустой выходной каталог; не подменяй прошлые отчёты.

## 2. Запись подтверждённого этапа

Подготовь JSON по схеме, например, скопировав [пример аудита](../examples/AUDIT.example.json) и заполнив фактические поля, затем:

```shell
python /path/to/audit-workflow/scripts/workflow_state.py record \
  --report-dir /path/to/candidate/audit \
  --payload /safe/staging/preflight-result.json
```

Первым должен быть `PREFLIGHT`. Остальные этапы — по порядку. Для `DOCS` сначала опубликуй Markdown через установленный `audit-docs/scripts/safe_writer.py`; затем передай в `output_files` реальный список файлов. Указания на ненайденные файлы, `state/*`, обход путей и символические ссылки отвергаются.

## 3. Возобновление и завершение

```shell
python /path/to/audit-workflow/scripts/workflow_state.py resume --report-dir /path/to/candidate/audit
python /path/to/audit-workflow/scripts/workflow_state.py finalize --report-dir /path/to/candidate/audit
```

`resume` возвращает следующий разрешённый этап, либо ошибку `STALE_INPUT`, если входные файлы изменились с начала аудита. Не перезапускай завершённый этап. Повтор после `FAILED`, `PARTIAL`, `BLOCKED` ограничен одной попыткой. `finalize` возвращает `COMPLETE` только после реальной записи и проверки документов, обязательных этапов и сохранения исходного состояния. При неполноте возвращается `PARTIAL/BLOCKED/FAILED`.

## 4. Отказ и восстановление

- `STALE_INPUT`: начни новый аудит с новым `report-dir`; не переноси старые выводы в новый запуск без повторной проверки.
- `workflow locked`: проверь, что никакой процесс не работает. Удаляй `.workflow.lock` **только вручную**, после подтверждения отсутствия активной записи.
- `missing/invalid manifest`: не пытайся угадать прошлые статусы; расследуй сбой, используй проверенный backup или новый запуск.
- `stage artifact checksum mismatch`: исходный JSON после записи изменился; не продолжай на потенциально недостоверных данных.
- Недоступны Python/зависимости/файлы: используй ручной режим передачи контекста, пометь `PERSISTENCE_UNAVAILABLE`, не выдавай его за гарантированное восстановление.

## 5. Безопасность и ограничения

Скрипт выполняет **только** операции над явным `<report-dir>/state/`. Не выполняет shell-команды и код проверяемого проекта. Исключает генерируемый каталог отчёта при вычислении SHA-256 цели, но **не** отслеживает модификации в исключённых кэшах. Предназначен для доверенной файловой системы без одновременно действующего злоумышленника (не является OS sandbox). Некоторые действия после аварийного прерывания могут оставить неактивные временные файлы или артефакты — это не признак завершённого этапа.

**Запрещено использовать `record` с фиктивными доказательствами лишь для получения статуса `COMPLETE`.** Скрипт проверяет форму и доступность файлов, но не истинность выводов LLM. Независимое подтверждение функциональной корректности в OpenCode, DeepSeek Harness, Claude Code, Codex и Cursor требует реальных интеграционных тестов.
