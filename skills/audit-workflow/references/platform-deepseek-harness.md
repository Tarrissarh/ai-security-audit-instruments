# Адаптер: DeepSeek Harness (не просто модель DeepSeek)

- Файловый провайдер **не является обязательным в каждом развёртывании**. Проверь, подключены ли пакеты `@deepseek-ai/dsh-skill` (registry), `@deepseek-ai/dsh-skill-filesystem` (discovery) и `@deepseek-ai/dsh-tool-skill` (consumer) либо их фактические эквиваленты.
- При настроенном провайдере поддерживаются `<project>/.dsh/skills/<name>/SKILL.md` и `<project>/.agents/skills/<name>/SKILL.md`, пользовательские и customSkillDirs. Глубоко вложенные `**/SKILL.md` в source root НЕ обнаруживаются: допускается одна папка скилла ниже root.
- `disable-model-invocation: true` скрывает автоматическую модельную загрузку; ручной режим генератора должен требовать новой команды человека независимо от реализации хоста.
- В отличие от обычного API DeepSeek, конкретный Harness — модульный хост с провайдерами Skills. При отсутствии provider не объявляй сам `SKILL.md` достаточной установкой.
- `skill` tool доступен только если consumer смонтирован. В остальных случаях применяй чтение файлов с маркировкой `READ_INSTRUCTIONS`.

Источник: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md
