# AI Audit & Tooling Skills

Кроссплатформенный комплект из **11 Agent Skills** для аудита, документирования, актуализации и разрешённой пользователем генерации AI-инструментов.

> Проверено: локальная структура, валидатор и синтетические тесты. **Фактическая работа в OpenCode, DeepSeek Harness, Claude Code, Codex и Cursor — `NOT_TESTED`** до реальных клиентских запусков.

## Состав дистрибутива

```text
ai-security-audit-skills/
├── skills/                  # ТОЛЬКО эти 11 каталогов копируются в AI-клиенты
│   ├── audit-workflow/
│   ├── audit-skill/
│   ├── audit-agent/
│   ├── audit-command/
│   ├── audit-mcp/
│   ├── audit-lsp/
│   ├── audit-hooks/
│   ├── audit-docs/
│   ├── audit-improve/
│   ├── audit-modernize/
│   └── ai-tool-generator/
├── scripts/                 # Установщик и статическая валидация
├── tests/                   # Unit- и регрессионные тесты
├── quality/                 # Синтетические проекты и эталонные результаты
├── integration/             # Инструментарий тестирования AI-клиентов
├── INSTALLATION.md          # Установка и проверка
├── WINDOWS.md               # Windows, PowerShell и пользовательские пути
├── COMPATIBILITY.md         # Ограничения платформ
├── TESTING.md               # Проверка качества
├── CHANGELOG.md             # Keep a Changelog
└── README.md
```

**Не копируйте** корневые `scripts/`, `tests/`, `quality/`, `integration/` или документацию в `.claude/skills/` и аналогичные папки. Каждый каталог `skills/<id>/` содержит полноценный `SKILL.md` и необходимые вспомогательные файлы, которые копируются **вместе** с ним.

## Устанавливаемые скиллы

| Skill                                                  | Назначение                                                    |
| ------------------------------------------------------ | ------------------------------------------------------------- |
| [audit-workflow](skills/audit-workflow/SKILL.md)       | Оркестратор, порядок этапов, контроль состояния               |
| [audit-skill](skills/audit-skill/SKILL.md)             | Проверка Skills                                               |
| [audit-agent](skills/audit-agent/SKILL.md)             | Проверка Agents                                               |
| [audit-command](skills/audit-command/SKILL.md)         | Проверка команд                                               |
| [audit-mcp](skills/audit-mcp/SKILL.md)                 | Проверка MCP                                                  |
| [audit-lsp](skills/audit-lsp/SKILL.md)                 | Проверка LSP                                                  |
| [audit-hooks](skills/audit-hooks/SKILL.md)             | Проверка Hooks                                                |
| [audit-docs](skills/audit-docs/SKILL.md)               | README.md, docs/, translations/                               |
| [audit-improve](skills/audit-improve/SKILL.md)         | Обоснованные улучшения                                        |
| [audit-modernize](skills/audit-modernize/SKILL.md)     | Проверка актуальности версий и подходов                       |
| [ai-tool-generator](skills/ai-tool-generator/SKILL.md) | Создание недостающих инструментов **только по явной команде** |

## Установка: Windows, Linux, macOS

Проектные каталоги:

| Клиент           | Путь для проекта (все ОС) |
| ---------------- | ------------------------- |
| OpenCode         | `.opencode/skills/`       |
| DeepSeek Harness | `.dsh/skills/`            |
| Claude Code      | `.claude/skills/`         |
| Codex            | `.agents/skills/`         |
| Cursor           | `.cursor/skills/`         |

Windows: `C:\Work\Project\.claude\skills\` (пример), персональная установка Claude Code — `%USERPROFILE%\.claude\skills\`. Linux/macOS: `/home/user/project/.claude/skills/` и `~/.claude/skills/`. Для остальных клиентов и нестандартного OpenCode XDG/DSH_HOME см. [WINDOWS.md](WINDOWS.md).

Подробности: [INSTALLATION.md](INSTALLATION.md).

### Безопасная установка через Python

Из корня распакованного архива, после ручной установки зависимостей из `requirements-validation.txt`:

```bash
python scripts/platform_compat.py stage --platform claude-code --project /path/to/project
python scripts/platform_compat.py stage --platform claude-code --project /path/to/project --apply
```

```powershell
py -3 .\scripts\platform_compat.py stage --platform claude-code --project 'C:\Work\Project'
py -3 .\scripts\platform_compat.py stage --platform claude-code --project 'C:\Work\Project' --apply
```

Первая команда лишь проверяет план; вторая записывает файлы в проект и не допускает перезаписи существующих Skills. Не запускайте `--apply` автоматически.

## Использование

1. Установите 11 каталогов из `skills/` в один подходящий Skills root клиента.
2. В чате клиента явно выберите `audit-workflow` и укажите путь к объекту аудита.
3. Предоставьте разрешения только на чтение объекта и запись в отдельный отчётный каталог.
4. Проверьте результат `README.md` и ссылки на `docs/` и `translations/`.
5. Отдельно разрешайте генератор, если аудитор обнаружил отсутствующий инструмент.

### Локальные тесты (без запуска AI-клиентов)

```bash
python -m pip install -r requirements-validation.txt
python scripts/validate_skills.py .
python -m unittest discover -s tests -v
```

Windows: `py -3 -m pip ...`, `py -3 .\scripts\validate_skills.py .`, `py -3 -m unittest ...`. Для локальной проверки требуется доверенная версия Python и зависимости, устанавливаемые пользователем. Исследуемые AI-инструменты не запускаются.

## Документация

- [PORTABILITY.md](PORTABILITY.md) — переносимые имена, Unicode/CRLF и Windows/Linux CI.
- [INSTALLATION.md](INSTALLATION.md) — проектная установка и команды.
- [WINDOWS.md](WINDOWS.md) — пользовательские и проектные пути Windows/Linux/macOS.
- [COMPATIBILITY.md](COMPATIBILITY.md) — ограничения клиентов.
- [TESTING.md](TESTING.md) — тестирование.
- [CHANGELOG.md](CHANGELOG.md) — история версий в стандартизированном формате.

В комплекте нет подтверждённого результата реального клиентского E2E. Локальный `PASS` — только структурная проверка.
