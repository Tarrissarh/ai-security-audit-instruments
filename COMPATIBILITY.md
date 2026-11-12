# Проверка кроссплатформенной совместимости

**Дата документальной сверки:** 2026-11-12. Проверялись пути обнаружения Skills, базовая модель загрузки, дополнительные требования, но **не выполнены реальные E2E-прогоны** в пяти клиентах.

| Клиент | SKILL.md | Условие | Межскилловые вызовы | Уверенность |
|---|---|---|---|---|
| OpenCode | Да | Скилл обнаружен + разрешение `skill` | штатный loader при разрешении; иначе чтение | Документация |
| DeepSeek Harness | Да, условно | Подключены `dsh-skill`, `dsh-skill-filesystem`, consumer | через смонтированный loader; иначе чтение | Документация |
| Claude Code | Да | `.claude/skills/` и актуальная версия клиента | прямой API не гарантируется одной фразой в SKILL.md | Документация |
| Codex | Да | `.agents/skills/`, допустимые права | явный/авто выбор; не предполагать универсальный API | Документация |
| Cursor | Да | `.cursor/skills/` или `.agents/skills/`, локальные/облачные ограничения | выбор в UI/моделью, без гарантий внутреннего API | Документация |

## Совместимость чего именно?

1. **Discovery** — видимость SKILL.md.
2. **Activation** — подгрузка инструкций вручную/моделью.
3. **Delegation** — возможность одного этапа реально вызвать другой; гарантируется не всегда.
4. **Capabilities** — чтение, запись, сеть, проверки — зависят от разрешений.
5. **Outputs** — запись отчётов возможна только при праве на каталог.
6. **Native artifacts** — Agents, Commands, Hooks, MCP-настройки различаются по платформам, не автоматически переносимы.

Нельзя превращать успех (1) в утверждение об успехе (2)–(6). Пороги поведения соответствуют [контракту оркестратора](audit-workflow/references/handoff-contract.md).

## Источники

- [Agent Skills specification](https://agentskills.io/specification)
- [OpenCode Skills](https://opencode.ai/docs/skills)
- [DeepSeek Harness filesystem provider](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md)
- [DeepSeek Harness Skills subsystem](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Codex Skills](https://learn.chatgpt.com/docs/build-skills)
- [Cursor Skills](https://cursor.com/docs/skills)

Ссылки отражают документацию на дату проверки; при новых версиях повторяй сверку.
