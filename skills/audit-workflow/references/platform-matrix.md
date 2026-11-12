# Матрица совместимости (проверено 2026-11-12)

| Хост             | Основной проектный корень Skills | Общий `.agents/skills`                                  | Важное отличие                                                                     |
| ---------------- | -------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| OpenCode         | `.opencode/skills/`              | Да                                                      | Использует `skill` tool и модель разрешений; идентификатор зависит от пути         |
| DeepSeek Harness | `.dsh/skills/`                   | Да, если включен `dsh-skill-filesystem`                 | Необходимо подключить provider и consumer `dsh-tool-skill`                         |
| Claude Code      | `.claude/skills/`                | Не полагаться на автоматическое чтение `.agents/skills` | Нативный `/skill-name`, дополнительные поля frontmatter                            |
| Codex            | `.agents/skills/`                | Да                                                      | Нет гарантированного межскиллового API: явный вызов и чтение файлов неэквивалентны |
| Cursor           | `.cursor/skills/`                | Да                                                      | В том числе совместимые каталоги Claude/Codex; remote/cloud требует синхронизации  |

Пути указаны **относительно корня проекта**. Также возможны пользовательские и дополнительные каталоги; проверь адаптер. Не устанавливай один и тот же ID в несколько одновременно сканируемых источников: приоритет и дубли зависят от хоста. `.agents/skills/` — удобный совместный каталог для OpenCode, DeepSeek Harness, Codex и Cursor, но не универсальная гарантия для Claude Code.

Проверяй по официальной документации при каждом обновлении пакета; список не фиксирует будущую совместимость.

Источники:

- OpenCode https://opencode.ai/docs/skills
- DeepSeek Harness https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md
- Claude Code https://code.claude.com/docs/en/skills
- Codex https://learn.chatgpt.com/docs/build-skills
- Cursor https://cursor.com/docs/skills
- Agent Skills https://agentskills.io/specification
