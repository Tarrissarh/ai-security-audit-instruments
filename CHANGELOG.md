# История версий

## v5 — 2026-11-12

- Добавлен одиннадцатый Skill `audit-workflow` с preflight, адаптерами OpenCode, DeepSeek Harness, Claude Code, Codex и Cursor.
- В шесть аудиторов добавлен режим оркестрации без рекурсивного вызова downstream Skills.
- В `audit-docs`, `audit-improve`, `audit-modernize` уточнён контракт исполнения в конвейере.
- `ai-tool-generator` стал ручным (`disable-model-invocation: true`) и получил матрицу генерируемых типов по платформам.
- Уточнена переносимость локальных путей OSV и запрет автоматического обновления базы.
- Добавлены статический валидатор, unit tests и ручные smoke-сценарии.
- Переписаны INSTALLATION, README и COMPATIBILITY с ссылками на официальные источники.

## v4 — 2026-11-12

- Шесть аудиторов, `audit-docs`, `audit-improve`, `audit-modernize` и `ai-tool-generator`.
- Модульные отчёты и переводы, реестр недостающих инструментов.

## v1-3 — 2026-11-12

- Инициализация и актуализация основных скиллов `agent`, `command`, `docs`, `hooks`, `lsp`, `mcp`, `skill`