"""Contrato estrito da base sintética; não faz imputação nem correção silenciosa."""
import numpy as np
import pandas as pd
from .data_source import obtain

CHANNELS = [f'Channel{i}' for i in range(5)]
MEDIA = [f'{c}_impression' for c in CHANNELS]
SPEND = [f'{c}_spend' for c in CHANNELS]
CONTROLS = ['competitor_sales_control', 'sentiment_score_control']
ORGANIC = ['Organic_channel0_impression']
NUMERIC = MEDIA + SPEND + CONTROLS + ORGANIC + ['Promo', 'conversions', 'revenue_per_conversion', 'population']
COLUMNS = ['geo', 'time'] + NUMERIC


def validate(df):
    """Erros físicos bloqueiam; ressalvas causais pertencem ao protocolo científico."""
    def require(condition, reason):
        if not condition:
            raise ValueError('BLOCKED: ' + reason)
    require(set(df.columns) == set(COLUMNS), 'colunas fora do contrato')
    require(len(df) == 6240, 'esperadas 6240 linhas')
    require(not df.isna().any().any(), 'valores ausentes')
    require(not df.duplicated(['geo', 'time']).any(), 'pares geo/time duplicados')
    require(set(df.geo) == {f'Geo{i}' for i in range(40)}, 'GEOs diferentes')
    dates = pd.date_range('2021-01-25', '2024-01-15', freq='7D').strftime('%Y-%m-%d').tolist()
    require(sorted(df.time.unique()) == dates, 'datas/periodicidade divergentes')
    require(df.groupby('geo').time.nunique().eq(156).all(), 'painel incompleto')
    require(all(pd.api.types.is_numeric_dtype(df[c]) for c in NUMERIC), 'tipos não numéricos')
    require(np.isfinite(df[NUMERIC].to_numpy()).all(), 'valores não finitos')
    require(df[[c for c in NUMERIC if c not in CONTROLS]].ge(0).all().all(), 'negativos fora dos controles')
    require(df.population.gt(0).all(), 'população não positiva')
    require(df.revenue_per_conversion.gt(0).all(), 'receita por conversão não positiva')
    require(df.groupby('geo').population.nunique().eq(1).all(), 'população varia no GEO')
    for m, s in zip(MEDIA, SPEND):
        require(df[m].eq(0).equals(df[s].eq(0)), f'zero incoerente entre {m} e {s}')
    for c in CONTROLS:
        require(df[c].lt(0).any() and df[c].gt(0).any(), f'sinais perdidos em {c}')
    require(df.Promo.eq(0).any() and df.Promo.gt(0).any() and df.Promo.nunique() > 2, 'Promo perdeu caráter contínuo')
    return df


def load_panel():
    raw = pd.read_csv(obtain())
    if 'Unnamed: 0' not in raw or not np.array_equal(raw['Unnamed: 0'].to_numpy(), np.arange(len(raw))):
        raise ValueError('BLOCKED: índice exportado não é a sequência original')
    df = raw.drop(columns='Unnamed: 0').copy()
    validate(df)
    df = df.assign(_order=df.geo.str.removeprefix('Geo').astype(int)).sort_values(['_order', 'time']).drop(columns='_order').reset_index(drop=True)
    # A ordenação não pode modificar volumes, inclusive com somas em ordem diferente.
    np.testing.assert_allclose(raw[NUMERIC].sum(), df[NUMERIC].sum(), rtol=1e-12, atol=1e-8)
    return df


def audit(df):
    validate(df)
    rows = []
    for c in NUMERIC:
        rows.append(dict(variable=c, dtype=str(df[c].dtype), min=float(df[c].min()), max=float(df[c].max()), zeros=int(df[c].eq(0).sum()), negatives=int(df[c].lt(0).sum()), total=float(df[c].sum()), status='PASS'))
    return pd.DataFrame(rows)


def structural_evidence(df):
    """Confere alegações selecionadas da EDA sem repetir a investigação completa."""
    pop = df.groupby('geo').population.first()
    totals = df.groupby('geo').conversions.sum()
    y = df.conversions
    between = df.groupby('geo').conversions.mean().var(ddof=0) / y.var(ddof=0)
    return {'rows': len(df), 'columns_clean': len(df.columns), 'geos': df.geo.nunique(), 'weeks': df.time.nunique(),
            'date_min': df.time.min(), 'date_max': df.time.max(), 'population_kpi_corr': float(pop.corr(totals)),
            'between_kpi_fraction': float(between), 'channel2_zero_fraction': float(df.Channel2_impression.eq(0).mean()),
            'channel3_zero_fraction': float(df.Channel3_impression.eq(0).mean()), 'promo_zero_fraction': float(df.Promo.eq(0).mean()),
            'channel2_spend_share': float(df.Channel2_spend.sum()/df[SPEND].sum().sum()),
            'channel3_spend_share': float(df.Channel3_spend.sum()/df[SPEND].sum().sum()),
            'population_once': float(pop.sum()), 'fractional_conversions_preserved': bool((y % 1 != 0).any())}
