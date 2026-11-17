# Changelog

Все значимые изменения проекта документируются здесь.
Формат соответствует [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
версии приведены к [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-17

### Added

- Новый профильный аудитор `audit-rules` для rules-файлов (`AGENTS.md`,
  `.cursor/rules`, `.windsurf/rules`, `.github/copilot-instructions.md`).
- `LICENSE` (MIT), `.gitignore`, `AGENTS.md`.
- Поле `version` во frontmatter всех скиллов.
- Критерии отнесения находок к уровню критичности в `report-template.md`.
- Рабочий пример аудита в `skills/audit-workflow/examples/`.

### Changed

- Зафиксированы версии зависимостей в `requirements.txt`.
- Тип `rules` добавлен в `TARGET_TYPE`, матрицу типов и реестр зависимостей.

### Removed

- Устаревший «полный архив»: `tests/`, `quality/`, `integration/`, корневые
  `scripts/` и сопутствующие корневые документы.
- Reference-файлы подсистемы «клиентский E2E / quality-бенчмарк»
  (`quality-benchmark.md`, `runtime-test-protocol.md`, `runtime-evidence.md`,
  `platform-runtime-verification.md`) и все ссылки на удалённый харнесс.
