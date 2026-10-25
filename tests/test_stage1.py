"""Testes de integridade e falhas reais; nenhuma instalação ou inferência."""
import ast
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml
from src.data_source import ROOT, obtain, verify_bytes, verify_provenance
from src.data_contract import load_panel, validate, MEDIA, SPEND, CONTROLS
from src.validation_design import make_holdout, coverage, aligned_mask

@pytest.fixture(scope='module')
def panel():
    return load_panel()

def test_hash_and_metadata():
    assert verify_provenance()==verify_bytes(obtain().read_bytes())

def test_corrupt_bytes_rejected():
    with pytest.raises(ValueError): verify_bytes(obtain().read_bytes()+b'\n')

def test_panel(panel):
    assert len(validate(panel))==6240

@pytest.mark.parametrize('damage',['duplicate','missing','population','negative_spend','broken_pair','control_sign','promo_binary','date','infinite','column'])
def test_contract_rejects_damage(panel,damage):
    x=panel.copy()
    if damage=='duplicate': x.iloc[1]=x.iloc[0]
    elif damage=='missing': x.loc[0,'conversions']=np.nan
    elif damage=='population': x.loc[0,'population']+=1
    elif damage=='negative_spend': x.loc[0,SPEND[0]]=-1
    elif damage=='broken_pair': x.loc[0,MEDIA[0]]=0;x.loc[0,SPEND[0]]=1
    elif damage=='control_sign': x[CONTROLS[0]]=x[CONTROLS[0]].abs()
    elif damage=='promo_binary': x['Promo']=(x.Promo>0).astype(int)
    elif damage=='date': x.loc[0,'time']='2021-01-26'
    elif damage=='infinite': x.loc[0,'conversions']=np.inf
    elif damage=='column': x=x.drop(columns=SPEND[0])
    with pytest.raises(ValueError): validate(x)

def test_original_values_preserved(panel):
    raw=pd.read_csv(obtain()).drop(columns='Unnamed: 0').set_index(['geo','time']).sort_index()
    pd.testing.assert_frame_equal(raw,panel.set_index(['geo','time']).sort_index())
    assert (panel.conversions%1!=0).any()

def test_mask_deterministic_independent_kpi_order(panel):
    a=make_holdout(panel)
    x=panel.sample(frac=1,random_state=1);x['conversions']=-999
    pd.testing.assert_frame_equal(a,make_holdout(x))
    assert a.is_holdout.sum()==936
    assert a.groupby('time').is_holdout.sum().eq(6).all()
    assert a.groupby('geo').is_holdout.sum().between(23,24).all()

def test_mask_coordinates_and_persistence(panel):
    a=make_holdout(panel)
    saved=pd.read_csv(ROOT/'data/splits/holdout_geo.csv')
    pd.testing.assert_frame_equal(a,saved)
    geos=sorted(panel.geo.unique(),reverse=True);times=sorted(panel.time.unique())
    mask=aligned_mask(a,geos,times)
    assert mask.shape==(40,156) and mask.sum()==936
    with pytest.raises(ValueError):aligned_mask(a.iloc[1:],geos,times)

def test_coverage_reconciles_exposure_spend(panel):
    g,t,c=coverage(panel,make_holdout(panel))
    assert len(g)==40 and len(t)==156
    allc=c[c.geo=='ALL'].groupby('channel')[['impressions','spend']].sum()
    for i in range(5):
        assert allc.loc[f'Channel{i}','impressions']==pytest.approx(panel[MEDIA[i]].sum())
        assert allc.loc[f'Channel{i}','spend']==pytest.approx(panel[SPEND[i]].sum())
    assert c.active.min()>0

def test_scope_registry_and_code():
    r=yaml.safe_load((ROOT/'configs/experiment_registry.yaml').read_text())
    assert all(x['status']=='planned' for x in r['experiments'])
    assert len(r['experiments'])>=25
    for path in (ROOT/'src').glob('*.py'):
        tree=ast.parse(path.read_text())
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        assert not set(calls)&{'sample_posterior','sample_prior','optimize','fit'}

def test_notebook_schema():
    import nbformat
    nb=nbformat.read(ROOT/'notebooks/01_DESENHO_CIENTIFICO_COLAB.ipynb',as_version=4)
    nbformat.validate(nb)
    assert len(list((ROOT/'notebooks').glob('*.ipynb')))==1

def test_meridian_input_spec_resolved_mask(panel):
    pytest.importorskip('meridian')
    from src.meridian_setup import build_input,build_spec,initialize_structure
    data=build_input(panel);split=make_holdout(panel);spec=build_spec(data,split)
    assert spec.effective_media_prior_type=='contribution'
    result=initialize_structure(data,spec,split)
    assert result['resolved_holdout_count']==936
    assert result['n_knots']==156
