# Генерация инструментов для разных хостов

| Тип     | Универсальная часть                      | Где нужна платформа                                     |
| ------- | ---------------------------------------- | ------------------------------------------------------- |
| Skill   | каталог `<name>/SKILL.md`, `references/` | каталог установки, механизмы делегирования, permissions |
| Agent   | роль, цель, лимиты, вход/выход           | схема native agent/subagent и разрешения, runtime       |
| Command | назначение, аргументы, проверка входов   | специфичный CLI/IDE формат и точки вызова               |
| MCP     | протокол, инструменты, схемы, runtime    | SDK/transport/auth/registration каждого клиента         |
| LSP     | спецификация LSP                         | клиент, capabilities, язык, способ подключения          |
| Hooks   | события, правило безопасности            | имена событий, форматы и политика запуска, конфигурация |

## Выбор назначения

- OpenCode: `.opencode/skills` (проект), штатный `skill` tool; другие артефакты согласно документации OpenCode.
- DeepSeek Harness: `.dsh/skills` при подключённом filesystem provider и tool-skill consumer. Не путай Harness с вызовом DeepSeek API.
- Claude Code: `.claude/skills`; нативные команды интегрированы со Skills; собственные агенты/хуки требуют соответствующего формата.
- Codex: `.agents/skills`; файлы агентов/правил и MCP настраивай по конкретной поддерживаемой среде.
- Cursor: `.cursor/skills` или `.agents/skills`; remote workers/Cloud Agents могут не иметь локальных персональных навыков.

Для каждого нестандартного инструмента перед генерацией **проверь** официальную документацию платформы и доступность интерфейса. Если нет данных — создай `SCAFFOLD` с открытыми вопросами, не называй полноценной интеграцией. Не включай созданные hooks/MCP/агентов без явного разрешения пользователя.

Ссылки: 
- `https://opencode.ai/docs/skills`,
- `https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md`,
- `https://code.claude.com/docs/en/skills`,
-  `https://learn.chatgpt.com/docs/build-skills`, 
-  `https://cursor.com/docs/skills`.
