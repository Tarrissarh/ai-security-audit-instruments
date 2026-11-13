# Изолированная проверка AI-клиента

В каталоге находятся скрипты для подготовки тестовых проектов, запуска клиента **только по явному подтверждению**, проверки свидетельств и оценки отдельных результатов аудита.

## Быстрый старт без запуска клиента

Из корня полного комплекта:

```sh
python integration/runtime/real_client.py probe
mkdir disposable-workspace
python integration/runtime/real_client.py prepare --platform codex --workspace ./disposable-workspace --fixture skill-clean
python integration/runtime/cli_e2e.py plan --workspace ./disposable-workspace
```

`--platform` принимает `opencode`, `deepseek-harness`, `claude-code`, `codex`, `cursor`. Для `prepare` нужен существующий пустой каталог. Программа устанавливает Skills, копирует синтетический пример в `subject/` и создаёт локальные контрольные данные; **модель не вызывается**.

## Проверка свидетельств

```sh
python integration/runtime/real_client.py assess --workspace ./disposable-workspace
python integration/runtime/cli_e2e.py verify --workspace ./disposable-workspace
python integration/runtime/compatibility_report.py --workspace ./disposable-workspace
```

Команды сверяют файловые данные и метаданные, но не устанавливают подлинность клиентского сеанса. Для настоящих клиентских испытаний, вывода журналов и расчёта качества используй [подробную инструкцию](CLIENT-TESTING.md).

**Статусы:** `NOT_TESTED`, `BLOCKED`, `REVIEW_REQUIRED`, `INVALID_EVIDENCE`; независимый `CLIENT_PASS` не присваивается автоматически.
