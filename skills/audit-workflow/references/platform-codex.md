# Адаптер: OpenAI Codex

- Проектная установка в `.agents/skills/<name>/SKILL.md`; пользовательская — `~/.agents/skills/<name>/SKILL.md` (Linux/macOS; Windows: `%USERPROFILE%\.agents\skills\<name>\SKILL.md`)). Codex использует прогрессивное раскрытие и может активировать Skill по описанию или явному упоминанию.
- Не утверждай, что Codex гарантирует программный вызов следующего Skill из предыдущего. Используй доступный механизм явного выбора/загрузки; если он не наблюдался — `READ_INSTRUCTIONS` с точным подтверждённым путём.
- Поддерживаемые расширения frontmatter и правила MCP/команд зависят от клиента/версии — не копируй автоматически Claude-specific поля или slash commands.
- Для `ai-tool-generator` обязательно отдельное согласие человека независимо от того, учитывается ли `disable-model-invocation` этим релизом Codex.
- В sandbox/режиме с ограниченными правами разделяй `readable` и `writable`; если запись запрещена, отдавай Markdown для ручного сохранения.

Источник: https://learn.chatgpt.com/docs/build-skills
