# Установка AI Audit & Tooling Skills

**Устанавливаемая часть комплекта:** только `skills/` — 11 каталогов, каждый содержит `SKILL.md` и необходимые `references/` / `scripts/` / `schemas/`.

**Документация и разработка:** файлы `README.md`, `CHANGELOG.md`, `WINDOWS.md`, `COMPATIBILITY.md`, `TESTING.md`, каталоги `scripts/`, `tests/`, `quality/`, `integration/` остаются в корне архива и не копируются в Skills root клиента.

## Рекомендуемые каталоги проекта

| AI-клиент        | Каталог проекта     | Windows пример                  | Linux/macOS пример                 |
| ---------------- | ------------------- | ------------------------------- | ---------------------------------- |
| OpenCode         | `.opencode/skills/` | `C:\Work\App\.opencode\skills\` | `/home/user/app/.opencode/skills/` |
| DeepSeek Harness | `.dsh/skills/`      | `C:\Work\App\.dsh\skills\`      | `/home/user/app/.dsh/skills/`      |
| Claude Code      | `.claude/skills/`   | `C:\Work\App\.claude\skills\`   | `/home/user/app/.claude/skills/`   |
| Codex            | `.agents/skills/`   | `C:\Work\App\.agents\skills\`   | `/home/user/app/.agents/skills/`   |
| Cursor           | `.cursor/skills/`   | `C:\Work\App\.cursor\skills\`   | `/home/user/app/.cursor/skills/`   |

Для путей **пользовательской** установки (`~/.claude/skills`, `~/.agents/skills` и т. п.) обязательно смотрите [Windows / Linux / macOS](WINDOWS.md): приведены `%USERPROFILE%` и альтернативы для OpenCode/DSH.

## Локальная установка без AI-клиента

Команды из корня распакованного архива, Python 3.10+ и установленные вручную зависимости из `requirements-validation.txt`:

```sh
python scripts/platform_compat.py smoke --platform opencode
python scripts/platform_compat.py stage --platform codex --project ./my-project
python scripts/platform_compat.py stage --platform codex --project ./my-project --apply
python scripts/platform_compat.py inspect --platform codex --project ./my-project
```

Windows PowerShell (вместо `./my-project` указан путь существующего проекта):

```powershell
py -3 .\scripts\platform_compat.py smoke --platform opencode
py -3 .\scripts\platform_compat.py stage --platform codex --project 'C:\Work\App'
py -3 .\scripts\platform_compat.py stage --platform codex --project 'C:\Work\App' --apply
py -3 .\scripts\platform_compat.py inspect --platform codex --project 'C:\Work\App'
```

`stage` **без** `--apply` составляет план, с `--apply` копирует только `skills/<id>/` и защищает существующие каталоги от перезаписи. Пользователь должен явно запросить установку. Не используйте инструмент для автоматической установки во время аудита.

## Ручное копирование

1. Создайте `<project>/.<client>/skills/` для нужного клиента (для Codex — `<project>/.agents/skills/`).
2. Скопируйте **все каталоги** из `skills/` туда целиком; не копируйте содержимое `skills/` в дополнительную вложенную директорию `skills/skills/`.
3. Убедитесь, что существует `<project>/.claude/skills/audit-workflow/SKILL.md` или аналогичный путь нужного клиента.
4. В тестовом проекте проверьте обнаружение и вызов `audit-workflow`; локальная проверка расположения — не E2E клиента.

В проекте с несколькими AI-клиентами некоторые из них одновременно сканируют `.agents/skills/`, `.claude/skills/` и собственные каталоги. Не создавайте дубликаты одного ID в разных корнях, видимых одному клиенту.

## Локальная валидация комплекта

```sh
python -m pip install -r requirements-validation.txt
python scripts/validate_skills.py .
python -m unittest discover -s tests -v
```

Для Windows используйте `py -3` вместо `python` при необходимости. Зависимости не устанавливаются автоматически; исследуемый код не запускается.

## Безопасность и совместимость

- `audit-workflow` — ручная или явная точка входа в полный аудит.
- `ai-tool-generator` — **только по явной команде человека**, не запускать автоматически.
- `skills/audit-docs/scripts/safe_writer.py` пишет отчёты только в разрешённый каталог; исходники не меняются.
- `skills/audit-workflow/scripts/workflow_state.py` управляет контрольными точками в разрешённом каталоге отчётов.
- Локальная база уязвимостей `vulndb/osv` (Windows `vulndb\osv`) обновляется только по разрешению; проверка источников не является выполнением исследуемого кода.
- См. [матрицу](COMPATIBILITY.md), [интеграционные тесты](TESTING.md) и [пути Windows](WINDOWS.md).

**Подтверждение работы в пяти AI-клиентах:** `NOT_TESTED` до реальных клиентских запусков.

## Проверки переносимости

Перед использованием на Windows посмотрите [PORTABILITY.md](PORTABILITY.md); автоматическая CI-проверка Windows подготовлена, но ещё не выполнена в этой среде.
