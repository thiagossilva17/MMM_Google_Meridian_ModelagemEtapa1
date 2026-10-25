"""Holdout balanceado independente do KPI; protocolo exclusivo para modelos GEO."""
import hashlib
import numpy as np
import pandas as pd
from .data_contract import CHANNELS


def make_holdout(coordinates, seed=20261025, per_week=6):
    """Permuta coordenadas por hash; ciclos garantem seis GEOs por semana.

    Seleção usa SOMENTE geo/time. Cada GEO tem 23 ou 24 semanas reservadas.
    A versão do algoritmo é hash-cycle-v1; não depende do gerador NumPy.
    """
    keys = coordinates[['geo', 'time']].copy()
    if keys.duplicated().any():
        raise ValueError('Coordenadas duplicadas')
    geos = sorted(keys.geo.unique(), key=lambda g: int(g[3:]))
    times = sorted(keys.time.unique())
    if len(keys) != len(geos)*len(times) or not 0 < per_week < len(geos):
        raise ValueError('Painel não retangular ou tamanho de holdout inválido')
    def rank(x):
        return hashlib.sha256(f'{seed}:{x}'.encode()).hexdigest()
    shuffled_geos = sorted(geos, key=rank)
    shuffled_times = sorted(times, key=rank)
    selected = {(shuffled_geos[(j*per_week+k) % len(geos)], t)
                for j, t in enumerate(shuffled_times) for k in range(per_week)}
    keys['is_holdout'] = [(g, t) in selected for g,t in keys.itertuples(index=False, name=None)]
    keys['_geo_order'] = keys.geo.map({g:i for i,g in enumerate(geos)})
    return keys.sort_values(['_geo_order', 'time']).drop(columns='_geo_order').reset_index(drop=True)


def coverage(df, split):
    if set(split.columns) != {'geo', 'time', 'is_holdout'} or split.is_holdout.dtype != bool:
        raise ValueError('Máscara precisa de booleanos e coordenadas explícitas')
    x = df.merge(split, on=['geo', 'time'], validate='one_to_one')
    if len(x) != len(df) or len(split) != len(df):
        raise ValueError('Máscara desalinhada ao painel')
    by_geo = x.groupby('geo').is_holdout.agg(['sum', 'count']).reset_index()
    by_week = x.groupby('time').is_holdout.agg(['sum', 'count']).reset_index()
    for table in [by_geo, by_week]:
        table['fraction'] = table['sum']/table['count']
    rows = []
    for geo, group in [('ALL', x)] + list(x.groupby('geo')):
        for channel in CHANNELS:
            for held, part in group.groupby('is_holdout'):
                exposure = part[channel+'_impression']
                rows.append(dict(geo=geo, channel=channel, subset='test' if held else 'train', n=len(part), active=int(exposure.gt(0).sum()), inactive=int(exposure.eq(0).sum()), active_fraction=float(exposure.gt(0).mean()), impressions=float(exposure.sum()), spend=float(part[channel+'_spend'].sum())))
    return by_geo, by_week, pd.DataFrame(rows)


def aligned_mask(split, geos, times):
    """Alinha pela coordenada da API, nunca pela posição incidental no CSV."""
    if split.duplicated(['geo', 'time']).any() or split.is_holdout.dtype != bool:
        raise ValueError('Máscara inválida')
    index = pd.MultiIndex.from_product([list(geos), list(times)], names=['geo', 'time'])
    s = split.set_index(['geo', 'time']).is_holdout
    if set(s.index) != set(index):
        raise ValueError('Coordenadas da máscara diferem da API')
    return s.reindex(index).to_numpy().reshape(len(geos), len(times))
