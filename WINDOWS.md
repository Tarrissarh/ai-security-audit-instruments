# Windows: расположение скиллов и команды

Для Windows 10/11 (PowerShell 5.1+ или PowerShell 7+) используйте **Windows-пути**, а не буквальный `~/` в строках для проводника. На Windows `$HOME` в PowerShell и `%USERPROFILE%` в CMD обычно обозначают домашний каталог пользователя. Для скриптов Python предпочтительна `Path.home()`, а для путей проекта — `Path(project) / ".claude" / "skills"` и аналогичные платформенные каталоги.

## Пути для пяти клиентов

| Клиент           | Проект: все ОС                                      | Linux/macOS: пользовательский                         | Windows: пользовательский                                                                                                    |
| ---------------- | --------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Claude Code      | `<project>/.claude/skills/`                         | `~/.claude/skills/`                                   | `%USERPROFILE%\.claude\skills\`                                                                                              |
| Codex            | `<project>/.agents/skills/`                         | `~/.agents/skills/`                                   | `%USERPROFILE%\.agents\skills\`                                                                                              |
| Cursor           | `<project>/.cursor/skills/` или `.agents/skills/`   | `~/.cursor/skills/`, `~/.agents/skills/`              | `%USERPROFILE%\.cursor\skills\`, `%USERPROFILE%\.agents\skills\`                                                             |
| DeepSeek Harness | `<project>/.dsh/skills/` или `.agents/skills/`      | `${DSH_HOME:-~/.dsh}/skills/` или `~/.agents/skills/` | `%DSH_HOME%\skills\` (если задана), иначе `%USERPROFILE%\.dsh\skills\`; также `%USERPROFILE%\.agents\skills\`                |
| OpenCode         | `<project>/.opencode/skills/` или `.agents/skills/` | `~/.config/opencode/skills/` или `~/.agents/skills/`  | Зависит от XDG и настроек OpenCode: проверьте фактический config root. Совместимый вариант — `%USERPROFILE%\.agents\skills\` |

**Примечание по OpenCode:** не предполагается, что `%APPDATA%\opencode\skills\` всегда равен `~/.config/opencode/skills/`. Путь зависит от активной конфигурации (например, `XDG_CONFIG_HOME`), версии и способа установки. Самый предсказуемый способ — проектный `.opencode/skills/` или поддерживаемый общий `.agents/skills/`.

Если используется WSL, Linux-пути WSL и Windows-пути хоста **не взаимозаменяемы**; устанавливайте скиллы в файловую систему, которую использует реально запущенный клиент.

## Структура архива

Из ZIP в клиент копируется **только содержимое каталога `skills/`**, то есть каждый каталог `skills/<skill-id>/` целиком. `scripts/`, `tests/`, `integration/`, `quality/` и корневые `.md` нужны для разработки, проверки и инструкций; их не следует помещать непосредственно в `.claude/skills` или другой клиентский Skills root.

## Установка в PowerShell (проект)

Запустите из корня распакованного пакета; укажите реальный путь проекта:

```powershell
$Project = 'C:\Work\MyProject'
$Destination = Join-Path $Project '.claude\skills'
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Get-ChildItem -Path '.\skills' -Directory | ForEach-Object {
    $Target = Join-Path $Destination $_.Name
    if (Test-Path -LiteralPath $Target) {
        throw "Скилл уже существует: $Target (перезапись запрещена)"
    }
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse
}
```

Замените `.claude\skills` на `.opencode\skills`, `.dsh\skills`, `.agents\skills` или `.cursor\skills` для соответствующей платформы. Этот сценарий **не запускает AI-клиент**. Он отказывается перезаписывать уже существующие каталоги.

Или воспользуйтесь Python-установщиком (предпочтительно для обнаружения конфликтующих ID):

```powershell
py -3 .\scripts\platform_compat.py stage --platform claude-code --project 'C:\Work\MyProject'
py -3 .\scripts\platform_compat.py stage --platform claude-code --project 'C:\Work\MyProject' --apply
py -3 .\scripts\platform_compat.py inspect --platform claude-code --project 'C:\Work\MyProject'
```

Второй вызов изменяет целевой проект и требует осознанного разрешения. Python-библиотеки для локальных валидаторов при необходимости устанавливаются отдельно, не автоматически:

```powershell
py -3 -m pip install -r .\requirements-validation.txt
py -3 .\scripts\validate_skills.py .
py -3 -m unittest discover -s tests -v
```

## Установка глобально на Windows

Не используйте глобальную установку без проверки реального домашнего каталога и конфликтов имён. Пример для Claude Code:

```powershell
$Destination = Join-Path $HOME '.claude\skills'
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
# Затем скопируйте сюда каталоги из .\skills\ аналогично проектному примеру.
```

## Linux/macOS: проектная установка

Из корня распакованного архива:

```bash
python3 scripts/platform_compat.py stage --platform claude-code --project /path/to/project
python3 scripts/platform_compat.py stage --platform claude-code --project /path/to/project --apply
```

## Источники для путей (сверка 2026-11-12)

- https://code.claude.com/docs/en/skills
- https://opencode.ai/docs/skills
- https://cursor.com/docs/skills
- https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md
- https://developers.openai.com/api/reference/cli

**Ограничение:** локальное размещение каталогов не означает реальную загрузку Skill в клиенте; требуется отдельный клиентский тест (`NOT_TESTED`, пока он не проведён).

## Проверка переносимости

См. [PORTABILITY.md](PORTABILITY.md): переносимые имена файлов, Windows read-only и CI. **Реальных запусков на NTFS в среде сборки не было.**
