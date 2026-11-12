# AI Audit & Tooling Skills v5

**11 переносимых AI Skills** для пассивного аудита, актуализации, планирования улучшений, документации и ручной генерации отсутствующих инструментов. Поддерживаются установки в OpenCode, DeepSeek Harness, Claude Code, Codex и Cursor при наличии соответствующего skill loader и файловых прав. **Проверка структуры ≠ проверка фактического выполнения в клиенте.**

## Комплект

| Скилл | Роль |
|---|---|
| [audit-workflow](audit-workflow/SKILL.md) | Главная точка входа, preflight, вызовы, статусы этапов и проверка отчётов |
| [audit-skill](audit-skill/SKILL.md) | Аудит Skills |
| [audit-agent](audit-agent/SKILL.md) | Аудит Agents |
| [audit-command](audit-command/SKILL.md) | Аудит Commands |
| [audit-mcp](audit-mcp/SKILL.md) | Аудит MCP |
| [audit-lsp](audit-lsp/SKILL.md) | Аудит LSP |
| [audit-hooks](audit-hooks/SKILL.md) | Аудит Hooks |
| [audit-improve](audit-improve/SKILL.md) | Конкретные предложения по улучшению, без правок |
| [audit-modernize](audit-modernize/SKILL.md) | Проверка актуальности технологий и решений, без правок |
| [audit-docs](audit-docs/SKILL.md) | Единый `README.md` + `docs/` + `translations/` |
| [ai-tool-generator](ai-tool-generator/SKILL.md) | **Только по явной команде человека** создание недостающих инструментов |

## Конвейер

```text
audit-workflow
    │ preflight + платформа + проверка доступности
    ▼
audit-skill | audit-agent | audit-command | audit-mcp | audit-lsp | audit-hooks
    │ доказательства, риски, инвентаризация
    ├─► audit-improve ──────────┐
    └─► audit-modernize ───────┤
                               ▼
                           audit-docs
                     README.md / docs/ / translations/
                               │
                               ▼
                     проверка + workflow-status.md

Отдельная явная команда человека ──► ai-tool-generator
```

## Изменения v5

- Добавлен `audit-workflow` с состояниями и контролем результатов; шесть аудиторов умеют вернуть результаты в конвейер без повторных downstream-вызовов.
- Для пяти хостов представлены [адаптеры](audit-workflow/references/platform-matrix.md) с путями установки, различиями skill loader, правами и ограничениями.
- Нет требования к несуществующему универсальному API вызова Skills: фиксируется `SKILL_CALL` или `READ_INSTRUCTIONS`.
- `ai-tool-generator` помечен `disable-model-invocation: true`, но обязательна независимая проверка явной команды человека.
- Путь к документам `references/` определяется относительно реально установленного Skill; ссылки на установленную копию не предполагают соседство с исследуемым проектом.
- Уточнён переносимый путь локальной OSV и запрет автоматической загрузки без разрешения.
- Добавлен независимый статический валидатор и инструкция ручного smoke-тестирования пяти клиентов.

## Быстрый старт

Установи все 11 папок скиллов в поддерживаемый каталог своей AI-среды. Рекомендованные пути и особенности см. [INSTALLATION.md](INSTALLATION.md). Пример запроса:

> Используй `audit-workflow` для статического аудита `./third-party/example-skill`. Целевая платформа — текущий клиент. Проверь зависимости, актуальность, предложи улучшения и создай README/docs/translations без изменения исходного кода. Не генерируй отсутствующие инструменты.

## Дополнительно

- [TESTING.md](TESTING.md) — тесты и обязательные ручные сценарии.
- [COMPATIBILITY.md](COMPATIBILITY.md) — ограничения по платформам и источники.
- [IMPROVEMENTS.md](IMPROVEMENTS.md) — дальнейшее развитие.
- [CHANGELOG.md](CHANGELOG.md) — изменения версий.
- Проверка локальной структуры: `python scripts/validate_skills.py .` из корня комплекта (это собственный статический валидатор, не код исследуемого инструмента).

**Безопасность:** все исходники проверяемых инструментов недоверенны, аудит не запускает их. Никакой MCP, hook или генератор не включается автоматически. Фактические проверки сред не выполнялись в этом архиве.
