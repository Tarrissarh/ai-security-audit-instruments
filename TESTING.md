# Проверка комплекта и качества аудита

Документ описывает актуальные тестовые сценарии. История добавления тестов и изменений хранится только в [CHANGELOG.md](CHANGELOG.md).

## 1. Локальная статическая регрессия

Из корня распакованного **полного** архива (доверенный Python и отдельно установленные зависимости; AI-клиенты не вызываются):

```sh
python -m pip install -r requirements-validation.txt
python scripts/validate_skills.py .
python -m unittest discover -s tests -v
```

На Windows при необходимости используй `py -3` вместо `python`. Проверяются структура 11 Skills, YAML Frontmatter, локальные Markdown-ссылки, запрет автоматического вызова генератора, контракты JSON и состояние, переносимые пути и безопасная файловая запись. Тесты не запускают исследуемые проекты.

## 2. Переносимость Windows/Linux

```sh
python -m unittest discover -s tests -p 'test_portability.py' -v
```

Тесты покрывают Unicode, Windows-зарезервированные имена, коллизии регистра, BOM, CRLF, поведение резервных копий и ограничения записи. [PORTABILITY.md](PORTABILITY.md) описывает границы подтверждения, в том числе непроверенное на реальном Windows NTFS поведение junctions и ACL. CI описан в `.github/workflows/portability.yml`, результаты Windows runner ещё не подтверждены.

## 3. Локальная проверка раскладки пяти платформ

```sh
python scripts/platform_compat.py smoke --platform opencode
python scripts/platform_compat.py smoke --platform deepseek-harness
python scripts/platform_compat.py smoke --platform claude-code
python scripts/platform_compat.py smoke --platform codex
python scripts/platform_compat.py smoke --platform cursor
```

Это smoke-тесты **установщика**, а не загрузчиков Skills. Для реального клиента используй [интеграционные сценарии](integration/runtime/CLIENT-TESTING.md).

## 4. JSON-контракты и восстановление

```sh
python -m unittest tests/test_workflow_state.py -v
python -m unittest tests/test_workflow_cli.py -v
```

Проверяются этапы `PREFLIGHT → AUDIT → IMPROVE → MODERNIZE → DOCS → VALIDATE`, проверка схемы, сохранение SHA-256, идемпотентность, повторные попытки, `STALE_INPUT`, недопустимые циклы и запрет генератора. Успешность локального state manager не означает, что модель вызывает скиллы самостоятельно.

## 5. Публикация отчётов и переводы

Используй пустой каталог, подготовь `staging/README.md`, `staging/docs/example.md`, `staging/translations/example.md` и соответствующие рабочие ссылки. Затем запусти:

```sh
python skills/audit-docs/scripts/safe_writer.py --staging staging --output sandbox/audit
```

Проверь SHA-256, резервные копии и отсутствие изменений вне разрешённого каталога; повторное выполнение без `--overwrite` должно блокироваться. `--overwrite` допускается только для ранее разрешённых документов и после резервирования. Скрипт не удаляет `RU.md` или `TRANSLATE.md`.

Для технической сохранности перевода:

```sh
python quality/scripts/translation_lint.py --source quality/examples/translations/original.md --translation quality/examples/translations/valid-ru.md
```

Автоматический линтер **не оценивает смысловую точность перевода**.

## 6. Качество аудиторов

Сначала прочитай [quality/README.md](quality/README.md). 12 тестовых инструментов из `quality/fixtures/` являются безопасными статическими примерами. Эталоны `quality/gold/` не передавай модели до получения её независимых ответов.

```sh
python quality/scripts/evaluate.py --predictions quality/examples/predictions-perfect.json
python quality/scripts/evaluate.py --predictions quality/examples/predictions-empty.json
```

Эти команды проверяют оценщик на подготовленных данных, **не качество действительных AI-аудитов**. Для настоящего измерения нужны ответы каждого клиента, а также ручная оценка инженерных рекомендаций.

## 7. Реальные клиентские сценарии

В отдельном тестовом проекте проверь discovery, activation, references, делегирование, формирование `README.md`, `docs/`, `translations/`, ошибки без прав записи/сети, блокировку автоматического `ai-tool-generator` и отсутствие изменения исходников. Каждая платформа должна иметь собственные данные о версии, настройках и наблюдаемых действиях. Без фактического запуска сохраняй `NOT_TESTED`.

Полная процедура: [интеграционные испытания](integration/runtime/CLIENT-TESTING.md). Актуальные статусы: [integration/MATRIX.md](integration/MATRIX.md).
