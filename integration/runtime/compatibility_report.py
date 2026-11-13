#!/usr/bin/env python3
"""Combine local integration evidence without claiming real-client compatibility.

Read-only. Does not run AI clients, evaluate untrusted fixture code, or install tools.
Operator-asserted PASS always remains REVIEW_REQUIRED until independently reviewed.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
from datetime import datetime, timezone
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
from typing import Any

# Импортирует модуль или имена, используемые в этом файле.
from real_client import CHECKS, assess, probe
# Импортирует модуль или имена, используемые в этом файле.
from cli_e2e import verify

# Сохраняет или обновляет вычисленное значение для последующих операций.
PLATFORM_ORDER = ('opencode', 'deepseek-harness', 'claude-code', 'codex', 'cursor')


# Объявляет функцию evaluate_workspace и её параметры.
def evaluate_workspace(workspace: Path) -> dict[str, Any]:
    # Описывает назначение блока в многострочной строке документации.
    """All checks are observational; never promote an operator's claim to PASS."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    workspace = Path(workspace)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        a = assess(workspace)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        platform = a['platform']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        client = verify(workspace)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checks = a['checks']
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        operator_pass = sorted(k for k in CHECKS if checks[k]['operator_assertion'] == 'PASS')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        failures = list(a.get('issues', [])) + list(client.get('issues', []))
        # Проверяет условие перед выполнением следующего блока.
        if not a['source_unchanged']:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            failures.append('UNAUTHORIZED_SOURCE_MODIFICATION')
        # Перебирает элементы набора для последовательной обработки.
        for key in operator_pass:
            # Проверяет условие перед выполнением следующего блока.
            if not checks[key]['evidence']:
                # Формирует часть выражения или передаёт аргумент в текущую операцию.
                failures.append(f'PASS_WITHOUT_EVIDENCE:{key}')
        # Возвращает вычисленный результат вызывающему коду.
        return {
            # Устанавливает поле workspace в словаре или описании.
            'workspace': str(workspace.resolve()), 'platform': platform,
            # Устанавливает поле fixture в словаре или описании.
            'fixture': a['fixture'],
            # Устанавливает поле local_evidence_check в словаре или описании.
            'local_evidence_check': a['status'],
            # Устанавливает поле run_log_check в словаре или описании.
            'run_log_check': client['status'],
            # Устанавливает поле client_run_records в словаре или описании.
            'client_run_records': client.get('runs_checked', 0),
            # Устанавливает поле source_unchanged в словаре или описании.
            'source_unchanged': a['source_unchanged'],
            # Устанавливает поле operator_pass_claims в словаре или описании.
            'operator_pass_claims': operator_pass,
            # Устанавливает поле checks в словаре или описании.
            'checks': {k: {'operator_status': checks[k]['operator_assertion'],
                           # Устанавливает поле independent_status в словаре или описании.
                           'independent_status': checks[k]['independent_client_verification'],
                           # Устанавливает поле evidence в словаре или описании.
                           'evidence': checks[k]['evidence']}
                       # Перебирает элементы набора для последовательной обработки.
                       for k in CHECKS},
            # Устанавливает поле issues в словаре или описании.
            'issues': sorted(set(failures)),
            # Устанавливает поле integration_status в словаре или описании.
            'integration_status': ('INVALID_EVIDENCE' if failures else
                                   # Формирует часть выражения или передаёт аргумент в текущую операцию.
                                   'REVIEW_REQUIRED' if operator_pass else
                                   # Формирует часть выражения или передаёт аргумент в текущую операцию.
                                   'NOT_TESTED'),
            # Устанавливает поле client_pass_certified в словаре или описании.
            'client_pass_certified': False,
        }
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        # Возвращает вычисленный результат вызывающему коду.
        return {
            # Устанавливает поле workspace в словаре или описании.
            'workspace': str(workspace), 'platform': None,
            # Устанавливает поле integration_status в словаре или описании.
            'integration_status': 'INVALID_EVIDENCE',
            # Устанавливает поле issues в словаре или описании.
            'issues': [f'{type(exc).__name__}: {exc}'],
            # Устанавливает поле client_pass_certified в словаре или описании.
            'client_pass_certified': False,
        }


# Объявляет функцию create_report и её параметры.
def create_report(workspaces: list[Path], * , include_probe: bool = True) -> dict[str, Any]:
    # Описывает назначение блока в многострочной строке документации.
    """Summarize supplied workspaces, not unobserved client behavior."""
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    result = [evaluate_workspace(p) for p in workspaces]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    probe_result = probe() if include_probe else None
    # Устанавливает поле clients в словаре или описании.
    clients: dict[str, dict[str, Any]] = {}
    # Перебирает элементы набора для последовательной обработки.
    for platform in PLATFORM_ORDER:
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        matches = [x for x in result if x.get('platform') == platform]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        clients[platform] = {
            # Устанавливает поле cli_on_path в словаре или описании.
            'cli_on_path': (probe_result['clients'][platform]['cli_present'] if probe_result else 'NOT_CHECKED'),
            # Устанавливает поле supplied_workspaces в словаре или описании.
            'supplied_workspaces': len(matches),
            # Устанавливает поле operator_pass_claims в словаре или описании.
            'operator_pass_claims': sum(len(m.get('operator_pass_claims', [])) for m in matches),
            # Устанавливает поле actual_client_e2e в словаре или описании.
            'actual_client_e2e': 'NOT_TESTED',
            # Устанавливает поле validated_client_pass в словаре или описании.
            'validated_client_pass': False,
            # Устанавливает поле status в словаре или описании.
            'status': ('INVALID_EVIDENCE' if any(m['integration_status'] == 'INVALID_EVIDENCE' for m in matches)
                       # Формирует часть выражения или передаёт аргумент в текущую операцию.
                       else 'REVIEW_REQUIRED' if any(m['integration_status'] == 'REVIEW_REQUIRED' for m in matches)
                       # Формирует часть выражения или передаёт аргумент в текущую операцию.
                       else 'NOT_TESTED'),
            # Устанавливает поле note в словаре или описании.
            'note': 'Independent client-skill execution has not been confirmed by this offline tool.',
        }
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    invalid = [r for r in result if r['integration_status'] == 'INVALID_EVIDENCE']
    # Возвращает вычисленный результат вызывающему коду.
    return {
        # Устанавливает поле report_schema в словаре или описании.
        'report_schema': 'v6.4.0',
        # Устанавливает поле generated_at в словаре или описании.
        'generated_at': datetime.now(timezone.utc).isoformat(),
        # Устанавливает поле execution_mode в словаре или описании.
        'execution_mode': 'READ_ONLY_OFFLINE',
        # Устанавливает поле clients_launched_by_this_tool в словаре или описании.
        'clients_launched_by_this_tool': 0,
        # Устанавливает поле client_pass_certified в словаре или описании.
        'client_pass_certified': False,
        # Устанавливает поле overall_status в словаре или описании.
        'overall_status': ('INVALID_EVIDENCE' if invalid else
                           # Формирует часть выражения или передаёт аргумент в текущую операцию.
                           'REVIEW_REQUIRED' if any(x['integration_status'] == 'REVIEW_REQUIRED' for x in result)
                           # Формирует часть выражения или передаёт аргумент в текущую операцию.
                           else 'NOT_TESTED'),
        # Устанавливает поле client_matrix в словаре или описании.
        'client_matrix': clients,
        # Устанавливает поле workspaces в словаре или описании.
        'workspaces': result,
        # Устанавливает поле limitations в словаре или описании.
        'limitations': [
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'Installed CLI presence is not evidence of skill discovery or activation.',
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'Operator-provided logs and SHA-256 hashes cannot prove independent provenance.',
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'The tool never returns PASS for a client, even when all local integrity checks pass.',
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            'Quality metrics require authentic LLM predictions and independent review.',
        ],
    }


# Объявляет функцию main и её параметры.
def main(argv = None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    p = argparse.ArgumentParser(description = __doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--workspace', type = Path, action = 'append', default = [],
                   # Сохраняет или обновляет вычисленное значение для последующих операций.
                   help = 'Prepared disposable integration workspace; repeat as needed')
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--no-probe', action = 'store_true', help = 'Avoid even PATH lookup')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args = p.parse_args(argv)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    report = create_report(args.workspace, include_probe = not args.no_probe)
    # Выводит диагностическую информацию о результате выполнения.
    print(json.dumps(report, indent = 2, ensure_ascii = False))
    # Возвращает вычисленный результат вызывающему коду.
    return 2 if report['overall_status'] == 'INVALID_EVIDENCE' else 0


# Проверяет условие перед выполнением следующего блока.
if __name__ == '__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    sys.exit(main())
