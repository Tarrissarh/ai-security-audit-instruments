# Матрица совместимости и испытаний

**Последняя подтверждённая локальная проверка:** 12.11.2026. Эта матрица отражает только выполненные проверки; повторное копирование пакета не проверяет AI-клиент.

| Клиент | Локальная подготовка Skills | Реальное обнаружение | Клиентский E2E | Метрики реального аудита |
|---|---|---|---|---|
| OpenCode | PASS | NOT_TESTED | NOT_TESTED | N/A |
| DeepSeek Harness | PASS | NOT_TESTED | NOT_TESTED | N/A |
| Claude Code | PASS | NOT_TESTED | NOT_TESTED | N/A |
| Codex | PASS | NOT_TESTED | NOT_TESTED | N/A |
| Cursor | PASS | NOT_TESTED | NOT_TESTED | N/A |

В использованной среде сборки не было настроенных клиентских CLI и провайдеров; клиентские журналы не предоставлены. **Подтверждённых реальных клиентских запусков: 0 из 5.**

`integration/runtime/compatibility_report.py` обрабатывает только предоставленные локальные свидетельства и не запускает клиента. `PASS` в операторском журнале остаётся `REVIEW_REQUIRED` до независимой оценки, а повреждённые свидетельства получают `INVALID_EVIDENCE`.

DeepSeek Harness: без подтверждённой read-only политики автоматическое исполнение `BLOCKED_READ_ONLY_UNVERIFIED`. Локальный тест установщика для DeepSeek Harness — не доказательство успешной загрузки.

Подробный сценарий: [CLIENT-TESTING.md](runtime/CLIENT-TESTING.md). Машинный снимок локальной подготовки: [offline-results.json](offline-results.json). Изолированные тестовые проекты подготавливаются по [runtime/README.md](runtime/README.md).
