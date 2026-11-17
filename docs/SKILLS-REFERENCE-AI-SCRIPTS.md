# Справочник по Python-скриптам и JSON-схемам (для ИИ)

> Часть набора «документация для ИИ» (см. [SKILLS-REFERENCE-AI.md](SKILLS-REFERENCE-AI.md)).
> Пофункциональный разбор доверенных вспомогательных скриптов набора. Ни один из этих
> скриптов не исполняет код проверяемого инструмента, не выходит в сеть и не
> устанавливает библиотеки.

---

## 0. Карта скриптов

| Скрипт | Расположение | Назначение | Зависимости |
| ------ | ------------ | ---------- | ----------- |
| `workflow_state.py` | `audit-workflow/scripts/` | менеджер состояния аудита (checkpoint) | `jsonschema`, `markdown-it-py` |
| `markdown_links.py` | `audit-workflow/scripts/` | проверка Markdown-ссылок (копия) | `markdown-it-py` |
| `safe_writer.py` | `audit-docs/scripts/` | безопасная публикация отчётов | `markdown-it-py` (+ `portable_names`, `markdown_links`) |
| `portable_names.py` | `audit-docs/scripts/` | проверка переносимости имён файлов | нет |
| `markdown_links.py` | `audit-docs/scripts/` | проверка Markdown-ссылок | `markdown-it-py` |

`requirements.txt`:
- `audit-workflow/scripts/requirements.txt`: `jsonschema>=4.20,<5`, `markdown-it-py>=3.0,<5`.
- `audit-docs/scripts/requirements.txt`: `markdown-it-py>=3.0,<5` (опционально, только для `safe_writer.py`).

---

## 1. `workflow_state.py` — детерминированный менеджер контрольных точек

**Назначение:** управляет доверенными метаданными аудита локально. Не вызывает LLM,
скиллы, тесты, сеть и не исполняет код аудируемого объекта. Пишет **только** в
явно переданный `<report_dir>/state/`. Публикация Markdown — отдельно через
`safe_writer.py`.

### 1.1 CLI

```
python workflow_state.py init      --target <path> --type <auto|skill|agent|command|mcp|lsp|hooks> --report-dir <path>
python workflow_state.py record    --report-dir <path> --payload <path/to/stage.json>
python workflow_state.py resume    --report-dir <path>
python workflow_state.py finalize  --report-dir <path>
```

- Выход — JSON на stdout; при ошибке — `{"status":"ERROR","message":...}` и код 1.

### 1.2 Константы

| Константа | Значение |
| --------- | -------- |
| `STAGES` | `('PREFLIGHT','AUDIT','IMPROVE','MODERNIZE','DOCS','VALIDATE')` |
| `MANDATORY` | `{'PREFLIGHT','AUDIT','DOCS','VALIDATE'}` |
| `RETRYABLE` | `{'FAILED','BLOCKED','PARTIAL'}` |
| `MAX_ATTEMPTS` | `2` |
| `MAX_PAYLOAD_BYTES` | `2 * 1024 * 1024` (2 МиБ) |
| `MAX_SOURCE_FILES` | `10_000` |
| `MAX_SOURCE_BYTES` | `256 * 1024 * 1024` (256 МиБ) |
| `EXCLUDED_DIRS` | `{'.git','node_modules','.venv','venv','__pycache__','.pytest_cache'}` |

### 1.3 Функции

| Функция | Назначение |
| ------- | ---------- |
| `now()` | UTC-время ISO8601 (секунды) |
| `digest(raw)` | SHA-256 hex |
| `safe_path(path)` | отказ от symlink в компонентах пути |
| `ensure_under(root, item)` | запрет выхода пути за каталог аудита |
| `schema(name)` | загрузка JSON-схемы из `schemas/` |
| `validate_schema(data, name)` | валидация по `Draft202012Validator` + `FormatChecker`, точная локализация ошибки |
| `source_fingerprint(target, report_dir)` | SHA-256 снимка исходников (пути + содержимое), отказ от symlink, лимиты размера/числа файлов |
| `atomic_json(path, value)` | запись через temp-файл + `os.replace`, `fsync`, права `0600` |
| `load_manifest(report)` | загрузка + валидация `state/manifest.json` |
| `exclusive_lock(report)` | создание `.workflow.lock` (`O_EXCL`), единственный писатель |
| `verify_source(manifest)` | `STALE_INPUT`, если SHA-256 цели изменился |
| `init(target, type, report)` | создание нового запуска, `run_id`, манифест |
| `read_artifact(report, value, expected_sha)` | чтение артефакта этапа с проверкой пути и SHA-256 |
| `stage_outputs(report, file_names, require_readme)` | проверка существования/непустоты выходных Markdown и их путей |
| `verify_report(report, docs_files, expected)` | проверка документов + SHA-256 + Markdown-ссылок |
| `edges_for(manifest, report, pending)` | построение графа вызовов (caller→callee) |
| `verify_invocations(manifest, report, pending)` | запрет циклов/рекурсии/дублей/`ai-tool-generator` |
| `prior_ready(manifest, stage)` | запрет запуска этапа до готовности предыдущих |
| `check_payload(manifest, report, obj)` | сверка JSON с запуском, контрактом и переходами |
| `record(report, payload)` | фиксация результата этапа (артефакт → манифест) |
| `next_stage(manifest)` | первый незавершённый этап |
| `resume(report)` | проверка исходников/артефактов, возврат следующего этапа |
| `finalize(report)` | итоговый статус после проверки обязательных этапов и документов |
| `main(argv)` | разбор CLI и диспетчеризация |

### 1.4 Логика `record` (пошагово)

1. `safe_path` для report и payload; payload — существующий JSON ≤ 2 МиБ.
2. `validate_schema(obj, 'stage-result')`.
3. `exclusive_lock` → `load_manifest` → `verify_source`.
4. Если артефакт этапа уже существует и равен новому — вернуть `UNCHANGED`.
5. Если статус не в `PENDING ∪ RETRYABLE` — ошибка (нельзя повторять разрешённый этап).
6. Если `attempts >= MAX_ATTEMPTS` — ошибка.
7. `prior_ready` + `check_payload`.
8. Записать `state/artifacts/<stage>-<attempt>.json` (сначала артефакт, потом манифест).
9. Для `DOCS COMPLETE` — зафиксировать `docs_checksums`.
10. Обновить манифест атомарно, вернуть `RECORDED`.

### 1.5 Логика `finalize`

- `FAILED`/`BLOCKED` в обязательных этапах → соответствующий итог.
- Не все обязательные `COMPLETE` → `PARTIAL`.
- `IMPROVE`/`MODERNIZE` в не-`COMPLETE` → `PARTIAL`.
- Иначе → проверить `DOCS`-артефакт и `verify_report` → `COMPLETE`.

### 1.6 Коды ошибок (сообщения)

`STALE_INPUT` (исходники изменились), `workflow locked`, `manifest.json not found`,
`stage artifact checksum mismatch`, `invalid <name> JSON at <location>`,
`path outside report directory`, `symlink in managed path/source`, `recursive call
into audit-workflow is forbidden`, `cyclic skill invocation graph detected`,
`ai-tool-generator cannot be called by audit-workflow` и др.

---

## 2. `safe_writer.py` — безопасная публикация отчётов

**Назначение:** публикует проверенные Markdown из staging в output с резервными
копиями и откатом. Не исполняет проверяемый код, не скачивает пакеты, не удаляет
`RU.md`/`TRANSLATE.md`, не пишет вне явного output-каталога.

### 2.1 CLI

```
python safe_writer.py --staging <dir> --output <dir> [--overwrite]
```

- Staging обязан содержать `README.md` (+ опц. `docs/**/*.md`, `translations/**/*.md`).
- `--overwrite` — разрешить замену существующих отчётов с побайтовой резервной копией.

### 2.2 Функции

| Функция | Назначение |
| ------- | ---------- |
| `sha256(data)` | SHA-256 hex |
| `_assert_no_symlinks(path)` | отказ от symlink/reparse point во всех компонентах |
| `_within(root, child)` | проверка, что путь остаётся в target-директории |
| `_collect(staging)` | сбор документов как исходных байтов (UTF-8/BOM/CRLF), проверка типов путей, пустых файлов, коллизий имён и Markdown-ссылок |
| `_atomic_replace(destination, data, old_mode)` | запись в temp + fsync + `os.replace` |
| `publish(staging, output, overwrite)` | полный цикл публикации с валидацией, резервным копированием и откатом |
| `main()` | CLI |

### 2.3 Допустимые пути в staging (строго)

`README.md`, либо `len(parts)>=2` и `parts[0] in ('docs','translations')` и суффикс
`.md`. Всё остальное — `PublishError`.

### 2.4 Порядок `publish`

1. Проверить отсутствие symlink в staging/output; staging и output не пересекаются.
2. `_collect` (валидировать **всё** до записи чего-либо).
3. `assert_no_existing_aliases(output, keys)` — отказ от Windows-алиасов имён.
4. Для каждого существующего файла: если `--overwrite` нет → ошибка; если read-only →
   ошибка; иначе сохранить `(bytes, mode)`.
5. Создать `output`, резервные копии в `output/.audit-backups/<stamp>-<uuid>/` (запись
   только новыми файлами `'xb'`, с верификацией SHA-256).
6. Записать каждый файл атомарно, проверить SHA-256.
7. При ошибке — откат записанных файлов в обратном порядке; при неполном откате —
   явная ошибка.

### 2.5 Возвращаемый JSON

```json
{
  "status": "COMPLETE",
  "output": "<dir>",
  "files_written": [...],
  "files_replaced": [...],
  "backups": "<dir или null>",
  "legacy_deleted": false
}
```
При ошибке: `{"status":"FAILED","error":"..."}` и код 1.

### 2.6 Явные не-гарантии

- Не защищает от конкурентного враждебного изменения файловой системы.
- Не гарантирует восстановление после выключения питания/принудительного завершения.
- Не является crash-safe транзакцией.

---

## 3. `portable_names.py` — переносимость имён файлов

**Назначение:** preflight переносимости имён (POSIX-валидные, но неоднозначные/невалидные
на Windows). Не является защитой от враждебных гонок файловой системы.

### 3.1 Константы

- `RESERVED_DEVICES` = `{CON, PRN, AUX, NUL} ∪ {COM1..COM9} ∪ {LPT1..LPT9}`.
- `INVALID_CHARACTERS` = `<>:"/\|?*`.

### 3.2 Функции

| Функция | Назначение |
| ------- | ---------- |
| `validate_component(name)` | отказ от `""`, `"."`, `".."`; завершающих пробелов/точек; запрещённых символов и управляющих (`< 32`); reserved device names (с учётом суперскриптов ¹²³ и отбрасывания расширения); длины > 255 UTF-16 единиц |
| `portable_key(relative_path)` | case-insensitive NFC-ключ; валидация каждой компоненты |
| `find_collisions(paths)` | поиск несовместимых имён и Windows-алиасов (различие только регистром/нормализацией) |
| `assert_no_existing_aliases(root, relative_paths)` | отказ от существующих записей, отличающихся регистром/нормализацией |
| `is_link_or_reparse_point(path)` | детект symlink и NTFS reparse point (junctions) через `FILE_ATTRIBUTE_REPARSE_POINT` (0x400) |

---

## 4. `markdown_links.py` — проверка Markdown-ссылок

**Назначение:** проверяет локальные ссылки в Markdown через CommonMark-токены
(`markdown-it-py`), не исполняя содержимое. Идентичный файл лежит в обоих скиллах.

### 4.1 API

```python
def check_markdown_links(root: Path, paths: list[Path] | None = None) -> tuple[list[str], list[str]]:
    """возвращает (errors, warnings)"""
```

### 4.2 Внутренние функции

| Функция | Назначение |
| ------- | ---------- |
| `_headings(path)` | список якорей заголовков (GitHub-style slug + суффиксы `-1`, `-2` для повторов) + HTML `id`/`name` |
| `_links(path)` | извлечение `href`/`src` из inline-токенов (link, image) с номером строки |

### 4.3 Логика проверки ссылки

- `//…` — пропуск; `scheme`/`netloc` (внешние URL) — пропуск (не проверяются локально).
- путь начинается с `/` — **warning** (site-root link, нельзя проверить локально).
- `\` или `\0` в пути — **error** (невалидный путь).
- цель разрешается относительно родителя; выход за `root` — **error** (`link escapes package`).
- цель не существует — **error**; не файл и не каталог — **error**.
- если есть фрагмент и цель — `.md`-файл: неизвестный якорь — **error**.

---

## 5. JSON-схемы

### 5.1 `manifest.schema.json` (v1.0)

`additionalProperties: false`. Обязательные поля: `schema_version` (`const "1.0"`),
`run_id` (`^[a-f0-9]{32}$`), `created_at`, `updated_at` (date-time), `target`,
`report_dir`, `state`, `stages`, `docs_checksums`.

- `target`: `{path: string, type: enum(skill|agent|command|mcp|lsp|hooks|auto), sha256: ^[a-f0-9]{64}$}`.
- `state`: `enum(RUNNING|COMPLETE|PARTIAL|BLOCKED|FAILED)`.
- `stages`: объект с ключами ровно шести этапов; у каждого `status` (enum
  `PENDING|COMPLETE|PARTIAL|SKIPPED|BLOCKED|FAILED`), `attempts` (int 0–2),
  `artifact` (string|null), `sha256` (null|`^[a-f0-9]{64}$`).
- `docs_checksums`: объект `{имя: sha256}`.

### 5.2 `stage-result.schema.json` (v1.0)

Обязательные поля: `schema_version`, `run_id`, `stage`, `status`, `method`,
`evidence`, `output_files`, `invocations`, `data`, `limitations`.

- `stage`: `enum(PREFLIGHT|AUDIT|IMPROVE|MODERNIZE|DOCS|VALIDATE)`.
- `status`: `enum(COMPLETE|PARTIAL|SKIPPED|BLOCKED|FAILED)`.
- `method`: `enum(SKILL_CALL|READ_INSTRUCTIONS|LOCAL_ANALYSIS|NOT_RUN)`.
- `evidence`: массив строк (1–2000 симв.), ≤ 10 000 шт.
- `output_files`: массив уникальных строк (1–1024 симв.), ≤ 10 000 шт.
- `invocations`: ≤ 100 объектов `{caller: string(1–128), callee: string(1–128)}`.
- `limitations`: массив строк ≤ 2000 симв., ≤ 1000 шт.

Условная структура `data` (через `allOf`/`if-then`):

| stage | required в `data` | детали |
| ----- | ----------------- | ------ |
| PREFLIGHT | `host_profile` | объект, `minProperties: 1` |
| AUDIT | `checked_files`, `findings` | `checked_files`: массив уникальных строк; `findings[]`: `{id, severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), file, evidence, confidence? (VERIFIED/DOCUMENTED/INFERRED/UNVERIFIED/NOT TESTED/NOT APPLICABLE)}` |
| IMPROVE | `proposals` | `proposals[]`: `{id, priority (P0/P1/P2/P3), what, why, how}` |
| MODERNIZE | `proposals` | `proposals[]`: `{id, verification_status (VERIFIED/.../NOT APPLICABLE), recommendation, source_url?, checked_at?}` |
| VALIDATE | `checks` | `checks[]`: `{name, status (PASSED/FAILED/NOT_TESTED)}` |

### 5.3 Пример (`examples/AUDIT.example.json`)

```json
{
  "schema_version": "1.0",
  "run_id": "00000000000000000000000000000000",
  "stage": "AUDIT",
  "status": "COMPLETE",
  "method": "READ_INSTRUCTIONS",
  "evidence": ["example/SKILL.md:1-9 — документация проверена"],
  "output_files": [],
  "invocations": [],
  "data": { "checked_files": ["example/SKILL.md"], "findings": [] },
  "limitations": ["Пример: вставьте фактический run_id из manifest.json"]
}
```

---

## 6. Замечания по корректному использованию

- Скрипты проверяют **форму и доступность** файлов, но **не истинность** выводов LLM.
  Запрещено использовать `record` с фиктивными доказательствами ради статуса `COMPLETE`.
- `workflow_state.py` управляет только `<report-dir>/state/`; `safe_writer.py` публикует
  только `README.md`, `docs/**/*.md`, `translations/**/*.md`. Области не пересекаются.
- Оба скрипта требуют ручной установки зависимостей из `requirements.txt`
  (автоматической установки нет).
- `safe_writer.py` никогда не удаляет `RU.md`/`TRANSLATE.md` — их миграция регулируется
  `references/safe-file-operations.md` и требует проверки и разрешения человека.

---

*Связанные документы:*
- [SKILLS-REFERENCE-AI.md](SKILLS-REFERENCE-AI.md) — основной справочник для ИИ.
- [SKILLS-GUIDE-RU.md](SKILLS-GUIDE-RU.md) — гайд для человека.
