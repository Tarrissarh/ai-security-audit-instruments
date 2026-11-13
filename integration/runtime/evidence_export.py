#!/usr/bin/env python3
"""Create a minimum-disclosure evidence bundle from prepared workspaces.

Default package contains metadata ONLY. Logs are excluded unless the user passes
--include-logs --privacy-reviewed. Never uploads data or certifies authenticity.
The operator must inspect every file before sharing the exported archive.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from compatibility_report import create_report
from cli_e2e import verify
from real_client import _evidence_file, _load_json

MAX_LOG_SIZE=512*1024

def export(workspaces: list[Path], output: Path, *, include_logs=False, privacy_reviewed=False) -> dict:
    """Экспортирует минимальные проверенные свидетельства; журналы включаются только по явному разрешению и после проверки конфиденциальности."""
    if include_logs and not privacy_reviewed:
        raise ValueError('--include-logs requires --privacy-reviewed')
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite output')
    if not workspaces:
        raise ValueError('specify at least one workspace')
    report=create_report(workspaces,include_probe=False)
    work=[]
    log_payloads=[]
    for i, raw in enumerate(workspaces,1):
        root=Path(raw)
        if root.is_symlink() or not root.is_dir():
            raise ValueError('unsafe workspace')
        root=root.resolve(strict=True)
        checks=verify(root)
        info=report['workspaces'][i-1]
        label=f'workspace-{i:03d}'
        work.append({
            'workspace_id':label,'platform':info.get('platform'),
            'integration_status':info['integration_status'],
            'fixture':info.get('fixture'), 'run_log_status':checks['status'],
            'run_records':checks['runs_checked'], 'source_unchanged':info.get('source_unchanged'),
            'operator_pass_claims':info.get('operator_pass_claims',[]),
            'issue_codes':[str(issue).split(':', 1)[0] for issue in info.get('issues',[])],
        })
        if include_logs:
            if checks['issues']:
                raise ValueError('refuse exporting logs with integrity errors')
            directory=root/'.integration-test/client-runs'
            if directory.is_symlink():
                raise ValueError('client-runs directory is symlinked')
            if directory.exists():
                # Экспортируем только журналы с проверенной контрольной суммой: произвольные файлы могут содержать секреты.
                for record_path in sorted(directory.glob('*.json')):
                    if record_path.is_symlink():
                        raise ValueError('symlinked run record')
                    run_record=_load_json(record_path)
                    for stream in ('stdout','stderr'):
                        rel=run_record[stream+'_file']
                        safe=_evidence_file(root,rel)
                        if not safe.is_file() or safe.stat().st_size>MAX_LOG_SIZE:
                            raise ValueError('invalid/oversized client log')
                        payload=safe.read_bytes()
                        if hashlib.sha256(payload).hexdigest()!=run_record[stream+'_sha256']:
                            raise ValueError('log hash mismatch')
                        log_payloads.append((f'{label}/logs/{safe.name}',payload))
    scrubbed={'schema_version':'1.0', 'client_pass_certified':False,
              'client_runs_performed_by_export':0,
              'workspaces':work,'logs_included':bool(log_payloads),
              'privacy_note':'Inspect archive contents before sharing. Even redacted logs can contain private text.',
              'source_note':'Local and operator-reported evidence is not proof of Skill activation.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SUMMARY.json',json.dumps(scrubbed,indent=2,ensure_ascii=False)+'\n')
        z.writestr('README.txt', 'AI Audit Skills evidence bundle. Local checks only; no CLIENT_PASS.\nReview every file for secrets before sharing.\n')
        for name, payload in log_payloads:
            z.writestr(name,payload)
    return {'status':'EXPORTED_UNVERIFIED_EVIDENCE','output':str(output),
            'workspace_count':len(work),'log_files':len(log_payloads),
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'client_pass_certified':False}

def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--include-logs',action='store_true')
    p.add_argument('--privacy-reviewed',action='store_true')
    args=p.parse_args(argv)
    try:
        print(json.dumps(export(args.workspace,args.output,include_logs=args.include_logs,
                                privacy_reviewed=args.privacy_reviewed),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,OSError,TypeError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'ERROR','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
