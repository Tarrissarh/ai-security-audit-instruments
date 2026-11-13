#!/usr/bin/env python3
"""Combine local integration evidence without claiming real-client compatibility.

Read-only. Does not run AI clients, evaluate untrusted fixture code, or install tools.
Operator-asserted PASS always remains REVIEW_REQUIRED until independently reviewed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from real_client import CHECKS, assess, probe
from cli_e2e import verify

PLATFORM_ORDER = ('opencode', 'deepseek-harness', 'claude-code', 'codex', 'cursor')

def evaluate_workspace(workspace: Path) -> dict[str, Any]:
    """All checks are observational; never promote an operator's claim to PASS."""
    workspace = Path(workspace)
    try:
        a = assess(workspace)
        platform = a['platform']
        client = verify(workspace)
        checks = a['checks']
        operator_pass = sorted(k for k in CHECKS if checks[k]['operator_assertion'] == 'PASS')
        failures = list(a.get('issues', [])) + list(client.get('issues', []))
        if not a['source_unchanged']:
            failures.append('UNAUTHORIZED_SOURCE_MODIFICATION')
        for key in operator_pass:
            if not checks[key]['evidence']:
                failures.append(f'PASS_WITHOUT_EVIDENCE:{key}')
        return {
            'workspace': str(workspace.resolve()), 'platform': platform,
            'fixture': a['fixture'],
            'local_evidence_check': a['status'],
            'run_log_check': client['status'],
            'client_run_records': client.get('runs_checked', 0),
            'source_unchanged': a['source_unchanged'],
            'operator_pass_claims': operator_pass,
            'checks': {k: {'operator_status': checks[k]['operator_assertion'],
                           'independent_status': checks[k]['independent_client_verification'],
                           'evidence': checks[k]['evidence']}
                       for k in CHECKS},
            'issues': sorted(set(failures)),
            'integration_status': ('INVALID_EVIDENCE' if failures else
                                   'REVIEW_REQUIRED' if operator_pass else
                                   'NOT_TESTED'),
            'client_pass_certified': False,
        }
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return {
            'workspace': str(workspace), 'platform': None,
            'integration_status': 'INVALID_EVIDENCE',
            'issues': [f'{type(exc).__name__}: {exc}'],
            'client_pass_certified': False,
        }

def create_report(workspaces: list[Path], * , include_probe: bool = True) -> dict[str, Any]:
    """Summarize supplied workspaces, not unobserved client behavior."""
    result = [evaluate_workspace(p) for p in workspaces]
    probe_result = probe() if include_probe else None
    clients: dict[str, dict[str, Any]] = {}
    for platform in PLATFORM_ORDER:
        matches = [x for x in result if x.get('platform') == platform]
        clients[platform] = {
            'cli_on_path': (probe_result['clients'][platform]['cli_present'] if probe_result else 'NOT_CHECKED'),
            'supplied_workspaces': len(matches),
            'operator_pass_claims': sum(len(m.get('operator_pass_claims', [])) for m in matches),
            'actual_client_e2e': 'NOT_TESTED',
            'validated_client_pass': False,
            'status': ('INVALID_EVIDENCE' if any(m['integration_status'] == 'INVALID_EVIDENCE' for m in matches)
                       else 'REVIEW_REQUIRED' if any(m['integration_status'] == 'REVIEW_REQUIRED' for m in matches)
                       else 'NOT_TESTED'),
            'note': 'Independent client-skill execution has not been confirmed by this offline tool.',
        }
    invalid = [r for r in result if r['integration_status'] == 'INVALID_EVIDENCE']
    return {
        'report_schema': 'compatibility-report',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'execution_mode': 'READ_ONLY_OFFLINE',
        'clients_launched_by_this_tool': 0,
        'client_pass_certified': False,
        'overall_status': ('INVALID_EVIDENCE' if invalid else
                           'REVIEW_REQUIRED' if any(x['integration_status'] == 'REVIEW_REQUIRED' for x in result)
                           else 'NOT_TESTED'),
        'client_matrix': clients,
        'workspaces': result,
        'limitations': [
            'Installed CLI presence is not evidence of skill discovery or activation.',
            'Operator-provided logs and SHA-256 hashes cannot prove independent provenance.',
            'The tool never returns PASS for a client, even when all local integrity checks pass.',
            'Quality metrics require authentic LLM predictions and independent review.',
        ],
    }

def main(argv = None) -> int:
    p = argparse.ArgumentParser(description = __doc__)
    p.add_argument('--workspace', type = Path, action = 'append', default = [],
                   help = 'Prepared disposable integration workspace; repeat as needed')
    p.add_argument('--no-probe', action = 'store_true', help = 'Avoid even PATH lookup')
    args = p.parse_args(argv)
    report = create_report(args.workspace, include_probe = not args.no_probe)
    print(json.dumps(report, indent = 2, ensure_ascii = False))
    return 2 if report['overall_status'] == 'INVALID_EVIDENCE' else 0

if __name__ == '__main__':
    sys.exit(main())
