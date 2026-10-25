"""Entrada única da auditoria; não executa inferência estatística."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
import numpy as np
import yaml
from .data_source import ROOT, verify_provenance
from .data_contract import load_panel, audit, structural_evidence
from .validation_design import make_holdout, coverage


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str)+'\n')


def run(with_api=True):
    tables = ROOT/'outputs/tables'; logs = ROOT/'outputs/logs'
    tables.mkdir(parents=True, exist_ok=True); logs.mkdir(parents=True, exist_ok=True)
    digest = verify_provenance()
    df = load_panel()
    audit(df).to_csv(tables/'data_audit.csv', index=False)
    evidence = structural_evidence(df)
    save_json(tables/'structural_evidence.json', evidence)
    checks = []
    for key, expected, tolerance in [('population_kpi_corr',.97,.01),('between_kpi_fraction',.68,.01),('channel2_zero_fraction',.643,.001),('channel3_zero_fraction',.027,.001),('promo_zero_fraction',.47,.01),('channel2_spend_share',.055,.002),('channel3_spend_share',.40,.01)]:
        checks.append(dict(indicator=key, observed=evidence[key], eda_rounded=expected, tolerance=tolerance,status='PASS' if abs(evidence[key]-expected)<=tolerance else 'REVIEW'))
    save_json(tables/'eda_reconciliation.json', checks)
    cfg = yaml.safe_load((ROOT/'configs/validation_design.yaml').read_text())['H-GEO']
    split = make_holdout(df[['geo','time']], seed=cfg['seed'], per_week=cfg['per_week'])
    (ROOT/'data/splits').mkdir(parents=True, exist_ok=True)
    split.to_csv(ROOT/'data/splits/holdout_geo.csv', index=False)
    geos,weeks,channels = coverage(df, split)
    for name,table in [('holdout_by_geo',geos),('holdout_by_week',weeks),('holdout_by_channel_geo',channels)]:
        table.to_csv(tables/f'{name}.csv',index=False)
    problems = []
    if not geos['sum'].between(23,24).all() or not weeks['sum'].eq(6).all():
        raise ValueError('BLOCKED: holdout perdeu balanceamento')
    for row in channels.itertuples():
        if row.active < cfg['coverage']['min_active_per_channel_per_geo_per_subset']:
            problems.append(f'{row.geo}/{row.channel}/{row.subset}: sem atividade')
    for (geo,ch),part in channels.groupby(['geo','channel']):
        by=part.set_index('subset');share=by.loc['test','spend']/by.spend.sum()
        if not .05 <= share <= .30:
            problems.append(f'{geo}/{ch}: fração de gasto teste {share:.4f} fora de [0.05,0.30]')
        if ch=='Channel2' and abs(by.loc['test','active_fraction']-by.loc['train','active_fraction'])>.20:
            problems.append(f'{geo}/{ch}: diferença de atividade >20pp')
    save_json(tables/'holdout_review.json', {'status':'REVIEW' if problems else 'PASS','alerts':problems, 'action':'Preservar máscara; investigar desequilíbrios antes de interpretar desempenho local.'})
    api = {'status':'BLOCKED','reason':'API não executada nesta chamada'}
    if with_api:
        from .meridian_setup import build_input,build_spec,inspect_input,prior_inventory,initialize_structure
        # Erro de API interrompe e é registrado; jamais convertido em PASS.
        try:
            data = build_input(df); ms=build_spec(data,split)
            api={'status':'PASS','tensors':inspect_input(data,df),'structure':initialize_structure(data,ms,split)}
            save_json(tables/'prior_inventory.json',prior_inventory(ms))
        except Exception as exc:
            save_json(logs/'api_validation.json',{'status':'BLOCKED','error':f'{type(exc).__name__}: {exc}'})
            raise
    save_json(logs/'api_validation.json',api)
    versions={}
    for package in ['google-meridian','numpy','pandas','tensorflow','tfp-nightly','jax','PyYAML','pytest','nbformat','nbclient','ipykernel']:
        try: versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package]='NOT_INSTALLED'
    artifacts={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(tables.glob('*'))}
    artifacts['data/splits/holdout_geo.csv']=hashlib.sha256((ROOT/'data/splits/holdout_geo.csv').read_bytes()).hexdigest()
    report={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Entrega 1: validação e configuração apenas','data_ready':'PASS','spec_ready':api['status'], 'scientific_readiness':'REVIEW','holdout_status':'REVIEW' if problems else 'PASS','holdout_train':int((~split.is_holdout).sum()),'holdout_test':int(split.is_holdout.sum()),'H_COMP':'PENDING_METHOD_DECISION','hosted_colab':'NOT_TESTED_IN_HOSTED_COLAB','posterior_sampling_executed':False,'prior_sampling_executed':False,'roi_estimated':False,'national_model_constructed':False,'source_sha256':digest,'python':platform.python_version(),'versions':versions,'artifact_sha256':artifacts}
    save_json(logs/'run_manifest.json',report)
    return report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--without-api',action='store_true')
    print(json.dumps(run(not parser.parse_args().without_api),indent=2,ensure_ascii=False))
