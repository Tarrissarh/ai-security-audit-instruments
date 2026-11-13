#!/usr/bin/env python3
"""v6.5: create a minimum-disclosure evidence bundle from prepared workspaces.

Default package contains metadata ONLY. Logs are excluded unless the user passes
--include-logs --privacy-reviewed. Never uploads data or certifies authenticity.
The operator must inspect every file before sharing the exported archive.
"""
# Импортирует модуль или имена, используемые в этом файле.
from __future__ import annotations
# Импортирует модуль или имена, используемые в этом файле.
import argparse
# Импортирует модуль или имена, используемые в этом файле.
import hashlib
# Импортирует модуль или имена, используемые в этом файле.
import json
# Импортирует модуль или имена, используемые в этом файле.
from pathlib import Path
# Импортирует модуль или имена, используемые в этом файле.
import sys
# Импортирует модуль или имена, используемые в этом файле.
import zipfile

# Импортирует модуль или имена, используемые в этом файле.
from compatibility_report import create_report
# Импортирует модуль или имена, используемые в этом файле.
from cli_e2e import verify
# Импортирует модуль или имена, используемые в этом файле.
from real_client import _evidence_file, _load_json

# Сохраняет или обновляет вычисленное значение для последующих операций.
MAX_LOG_SIZE=512*1024


# Объявляет функцию export и её параметры.
def export(workspaces: list[Path], output: Path, *, include_logs=False, privacy_reviewed=False) -> dict:
    # Проверяет условие перед выполнением следующего блока.
    if include_logs and not privacy_reviewed:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('--include-logs requires --privacy-reviewed')
    # Проверяет условие перед выполнением следующего блока.
    if output.exists() or output.is_symlink():
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('refusing to overwrite output')
    # Проверяет условие перед выполнением следующего блока.
    if not workspaces:
        # Прерывает операцию с диагностическим исключением.
        raise ValueError('specify at least one workspace')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    report=create_report(workspaces,include_probe=False)
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    work=[]
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    log_payloads=[]
    # Перебирает элементы набора для последовательной обработки.
    for i, raw in enumerate(workspaces,1):
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        root=Path(raw)
        # Проверяет условие перед выполнением следующего блока.
        if root.is_symlink() or not root.is_dir():
            # Прерывает операцию с диагностическим исключением.
            raise ValueError('unsafe workspace')
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        root=root.resolve(strict=True)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        checks=verify(root)
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        info=report['workspaces'][i-1]
        # Сохраняет или обновляет вычисленное значение для последующих операций.
        label=f'workspace-{i:03d}'
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        work.append({
            # Устанавливает поле workspace_id в словаре или описании.
            'workspace_id':label,'platform':info.get('platform'),
            # Устанавливает поле integration_status в словаре или описании.
            'integration_status':info['integration_status'],
            # Устанавливает поле fixture в словаре или описании.
            'fixture':info.get('fixture'), 'run_log_status':checks['status'],
            # Устанавливает поле run_records в словаре или описании.
            'run_records':checks['runs_checked'], 'source_unchanged':info.get('source_unchanged'),
            # Устанавливает поле operator_pass_claims в словаре или описании.
            'operator_pass_claims':info.get('operator_pass_claims',[]),
            # Устанавливает поле issue_codes в словаре или описании.
            'issue_codes':[str(issue).split(':', 1)[0] for issue in info.get('issues',[])],
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        })
        # Проверяет условие перед выполнением следующего блока.
        if include_logs:
            # Проверяет условие перед выполнением следующего блока.
            if checks['issues']:
                # Прерывает операцию с диагностическим исключением.
                raise ValueError('refuse exporting logs with integrity errors')
            # Сохраняет или обновляет вычисленное значение для последующих операций.
            directory=root/'.integration-test/client-runs'
            # Проверяет условие перед выполнением следующего блока.
            if directory.is_symlink():
                # Прерывает операцию с диагностическим исключением.
                raise ValueError('client-runs directory is symlinked')
            # Проверяет условие перед выполнением следующего блока.
            if directory.exists():
                # Only export logs explicitly referenced by an integrity-checked run record.
                # Untracked .txt files must never be collected by globbing the directory.
                # Перебирает элементы набора для последовательной обработки.
                for record_path in sorted(directory.glob('*.json')):
                    # Проверяет условие перед выполнением следующего блока.
                    if record_path.is_symlink():
                        # Прерывает операцию с диагностическим исключением.
                        raise ValueError('symlinked run record')
                    # Сохраняет или обновляет вычисленное значение для последующих операций.
                    run_record=_load_json(record_path)
                    # Перебирает элементы набора для последовательной обработки.
                    for stream in ('stdout','stderr'):
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        rel=run_record[stream+'_file']
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        safe=_evidence_file(root,rel)
                        # Проверяет условие перед выполнением следующего блока.
                        if not safe.is_file() or safe.stat().st_size>MAX_LOG_SIZE:
                            # Прерывает операцию с диагностическим исключением.
                            raise ValueError('invalid/oversized client log')
                        # Сохраняет или обновляет вычисленное значение для последующих операций.
                        payload=safe.read_bytes()
                        # Проверяет условие перед выполнением следующего блока.
                        if hashlib.sha256(payload).hexdigest()!=run_record[stream+'_sha256']:
                            # Прерывает операцию с диагностическим исключением.
                            raise ValueError('log hash mismatch')
                        # Формирует часть выражения или передаёт аргумент в текущую операцию.
                        log_payloads.append((f'{label}/logs/{safe.name}',payload))
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    scrubbed={'schema_version':'6.5', 'client_pass_certified':False,
              # Устанавливает поле client_runs_performed_by_export в словаре или описании.
              'client_runs_performed_by_export':0,
              # Устанавливает поле workspaces в словаре или описании.
              'workspaces':work,'logs_included':bool(log_payloads),
              # Устанавливает поле privacy_note в словаре или описании.
              'privacy_note':'Inspect archive contents before sharing. Even redacted logs can contain private text.',
              # Устанавливает поле source_note в словаре или описании.
              'source_note':'Local and operator-reported evidence is not proof of Skill activation.'}
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    output.parent.mkdir(parents=True,exist_ok=True)
    # Открывает управляемый контекст и гарантирует его корректное завершение.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        z.writestr('SUMMARY.json',json.dumps(scrubbed,indent=2,ensure_ascii=False)+'\n')
        # Формирует часть выражения или передаёт аргумент в текущую операцию.
        z.writestr('README.txt', 'AI Audit Skills v6.5 evidence bundle. Local checks only; no CLIENT_PASS.\nReview every file for secrets before sharing.\n')
        # Перебирает элементы набора для последовательной обработки.
        for name, payload in log_payloads:
            # Формирует часть выражения или передаёт аргумент в текущую операцию.
            z.writestr(name,payload)
    # Возвращает вычисленный результат вызывающему коду.
    return {'status':'EXPORTED_UNVERIFIED_EVIDENCE','output':str(output),
            # Устанавливает поле workspace_count в словаре или описании.
            'workspace_count':len(work),'log_files':len(log_payloads),
            # Устанавливает поле sha256 в словаре или описании.
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            # Устанавливает поле client_pass_certified в словаре или описании.
            'client_pass_certified':False}


# Объявляет функцию main и её параметры.
def main(argv=None) -> int:
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    p=argparse.ArgumentParser(description=__doc__)
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--workspace',type=Path,action='append',required=True)
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--output',type=Path,required=True)
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--include-logs',action='store_true')
    # Настраивает аргументы, параметры или состояние объекта.
    p.add_argument('--privacy-reviewed',action='store_true')
    # Сохраняет или обновляет вычисленное значение для последующих операций.
    args=p.parse_args(argv)
    # Начинает блок с контролируемой обработкой исключений.
    try:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps(export(args.workspace,args.output,include_logs=args.include_logs,
                                # Сохраняет или обновляет вычисленное значение для последующих операций.
                                privacy_reviewed=args.privacy_reviewed),ensure_ascii=False,indent=2))
        # Возвращает вычисленный результат вызывающему коду.
        return 0
    # Перехватывает указанное исключение для безопасной обработки.
    except (ValueError,KeyError,OSError,TypeError,json.JSONDecodeError) as exc:
        # Выводит диагностическую информацию о результате выполнения.
        print(json.dumps({'status':'ERROR','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        # Возвращает вычисленный результат вызывающему коду.
        return 1

# Проверяет условие перед выполнением следующего блока.
if __name__=='__main__':
    # Формирует часть выражения или передаёт аргумент в текущую операцию.
    sys.exit(main())
