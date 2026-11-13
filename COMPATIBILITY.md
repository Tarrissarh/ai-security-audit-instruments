# Совместимость с AI-клиентами

**Документальная сверка:** 12.11.2026. **Реальные запуски в клиентах:** не проводились. Локальная установка и проверка файлов не доказывают фактическую активацию Skill.

| Клиент           | Каталог в проекте                      | Требования                                                     | Локальная установка | Skill discovery / E2E |
| ---------------- | -------------------------------------- | -------------------------------------------------------------- | ------------------- | --------------------- |
| OpenCode         | `.opencode/skills/`, `.agents/skills/` | Разрешение `skill`, исключение конфликтующих ID                | PASS                | NOT_TESTED            |
| DeepSeek Harness | `.dsh/skills/`, `.agents/skills/`      | Registry, filesystem provider, consumer; один уровень каталога | PASS                | NOT_TESTED            |
| Claude Code      | `.claude/skills/`                      | Поддерживаемая версия и разрешения                             | PASS                | NOT_TESTED            |
| Codex            | `.agents/skills/`                      | Workspace и sandbox-ограничения                                | PASS                | NOT_TESTED            |
| Cursor           | `.cursor/skills/`, `.agents/skills/`   | Режим запуска, правила доступа и отсутствие дубликатов         | PASS                | NOT_TESTED            |

На момент локальной проверки клиентские CLI не были обнаружены. `CLI_PRESENT` или `LOCAL_INSTALL_PASS` никогда не равнозначны `CLIENT_PASS`. Машинные локальные результаты и актуальная матрица: [integration/MATRIX.md](integration/MATRIX.md).

## Что именно необходимо подтвердить

1. **Discovery:** загрузчик видит установленный `SKILL.md`.
2. **Activation:** действительно загружены инструкции, а не просто упомянуто имя.
3. **Delegation:** наблюдаются корректные переходы между аудитором, `audit-improve`, `audit-modernize` и `audit-docs`.
4. **Capabilities:** разрешены только необходимые операции; изоляция и ограничения подтверждены.
5. **Outputs:** создан отчёт с `README.md`, `docs/`, `translations/`, оригиналы не изменены.
6. **Native artifacts:** создаваемые Commands, Agents, MCP и Hooks учитывают специфику конкретного клиента.

Успех одного уровня не доказывает успех следующих. Статусы `DOCUMENTED`, `LOCAL_STATIC_PASS`, `NOT_TESTED`, `BLOCKED`, `REVIEW_REQUIRED`, `CLIENT_PASS` не смешивать.

## Оркестрация и сохранение результатов

При наличии доверенного Python и зависимостей, перечисленных в `skills/audit-workflow/scripts/requirements.txt`, возможен режим `PERSISTENT` с JSON-контрактами и checkpoint-файлами. При запрете исполнения или записи используется `MANUAL` и статус `PERSISTENCE_UNAVAILABLE`. Это собственная функциональность комплекта, а не доказательство того, что каждый AI-клиент способен вызывать другие скиллы.

Применяй [контракт передачи данных](skills/audit-workflow/references/handoff-contract.md). Запись документации в чужой каталог требует разрешения. Клиентские права не заменяются инструкциями в `SKILL.md`.

## Ограничения безопасности клиентов

- **DeepSeek Harness:** документированный `dsh --profile headless` не доказывает режим только для чтения. Автоматический тестовый запуск блокируется как `BLOCKED_READ_ONLY_UNVERIFIED`, пока не обеспечены подтверждённые ограничения.
- **OpenCode:** проверяй схему `permissions`/`policies` установленной версии. Старые примеры конфигурации нельзя считать действующими.
- **Cursor:** обнаружение бинарника `agent` неоднозначно; проверяй происхождение CLI, а для теста без записи — доступность ограничительного режима.
- **Все платформы:** отсутствие клиента означает `NOT_TESTED`; SHA-256 журнальных файлов сам по себе не подтверждает их происхождение.

Для реальных испытаний используется [руководство](integration/runtime/CLIENT-TESTING.md); установка пакета описана в [INSTALLATION.md](INSTALLATION.md), Windows-пути — в [WINDOWS.md](WINDOWS.md).

## Официальные источники

- [Agent Skills](https://agentskills.io/specification)
- [OpenCode Skills](https://opencode.ai/docs/skills)
- [DeepSeek Harness filesystem provider](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md)
- [DeepSeek Harness Skills subsystem](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Codex Skills](https://learn.chatgpt.com/docs/build-skills)
- [Cursor Skills](https://cursor.com/docs/skills)

Ссылки отражают документацию на дату сверки; перед следующим клиентским тестом проверяй текущие требования.
