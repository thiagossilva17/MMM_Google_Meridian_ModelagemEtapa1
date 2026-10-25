"""Constrói e inspeciona objetos Meridian 2.1.0; não contém inferência."""
import dataclasses
import importlib.metadata
import numpy as np
import yaml
from .data_source import ROOT
from .data_contract import validate, MEDIA, SPEND, CHANNELS, CONTROLS, ORGANIC
from .validation_design import aligned_mask


def check_version():
    actual = importlib.metadata.version('google-meridian')
    if actual != '2.1.0':
        raise RuntimeError(f'BLOCKED: requerido Meridian 2.1.0; encontrado {actual}')
    return actual


def build_input(df):
    check_version()
    validate(df)
    from meridian.data import load
    coords = load.CoordToColumns(geo='geo', time='time', kpi='conversions', population='population',
        media=MEDIA, media_spend=SPEND, controls=CONTROLS, organic_media=ORGANIC,
        non_media_treatments=['Promo'])
    # Sem revenue_per_kpi: KPI primário permanece conversões; monetização pendente.
    data = load.DataFrameDataLoader(df=df.copy(), coord_to_columns=coords, kpi_type='non_revenue',
        media_to_channel=dict(zip(MEDIA, CHANNELS)), media_spend_to_channel=dict(zip(SPEND, CHANNELS))).load()
    inspect_input(data, df)
    return data


def inspect_input(data, df):
    tensors = {}
    for name, shape in {'kpi':(40,156), 'population':(40,), 'media':(40,156,5),
                        'media_spend':(40,156,5), 'controls':(40,156,2),
                        'organic_media':(40,156,1), 'non_media_treatments':(40,156,1)}.items():
        arr = getattr(data, name)
        if arr is None or arr.shape != shape or not np.isfinite(arr.values).all():
            raise ValueError(f'BLOCKED: tensor {name} inválido')
        tensors[name] = {'shape':list(arr.shape), 'dims':list(arr.dims)}
    if list(data.media.media_channel.values) != CHANNELS:
        raise ValueError('Ordem dos canais divergente')
    # Reconciliação célula a célula detecta troca de canais e de coordenadas.
    aligned = df.set_index(['geo', 'time']).reindex(__import__('pandas').MultiIndex.from_product([data.geo.values, data.time.values]))
    for name, cols in [('kpi',['conversions']), ('media',MEDIA), ('media_spend',SPEND), ('controls',CONTROLS), ('organic_media',ORGANIC), ('non_media_treatments',['Promo'])]:
        np.testing.assert_allclose(getattr(data,name).values.reshape(6240,-1), aligned[cols].to_numpy(), rtol=2e-6, atol=1e-6)
    return tensors


def build_spec(data, split=None):
    check_version()
    from meridian.model import spec, prior_distribution
    cfg = yaml.safe_load((ROOT/'configs/baseline_geo.yaml').read_text())
    kwargs = {key: item['value'] for key,item in cfg['model_spec'].items()}
    if split is not None:
        aligned_mask(split, data.geo.values, data.time.values)
        entries = [spec.GeoHoldoutSpec(geos=[geo], date_ranges=[spec.DateRange(start_date=t, end_date=t) for t in part.loc[part.is_holdout,'time']]) for geo,part in split.groupby('geo')]
        kwargs['holdout'] = spec.HoldoutSpec(spec=entries)
    return spec.ModelSpec(prior=prior_distribution.PriorDistribution(), **kwargs)


def prior_inventory(model_spec):
    """Parâmetros configurados; nenhuma amostra da prior ou posterior."""
    rows = []
    for field in dataclasses.fields(model_spec.prior):
        dist = getattr(model_spec.prior, field.name)
        pars = {}
        for key, val in dist.parameters.items():
            if key in {'name','validate_args','allow_nan_stats'}:
                continue
            try:
                pars[key] = np.asarray(val).tolist()
            except (TypeError, ValueError):
                pars[key] = str(val)
        rows.append({'parameter':field.name, 'distribution':type(dist).__name__, 'parameters':pars})
    return rows


def initialize_structure(data, model_spec, split=None):
    """Inicializa apenas estrutura para validar holdout resolvido e knots."""
    from meridian.model import model
    mmm = model.Meridian(input_data=data, model_spec=model_spec)
    result = {'initialization':'PASS', 'n_knots':int(mmm.knot_info.n_knots)}
    if split is not None:
        expected = aligned_mask(split, data.geo.values, data.time.values)
        actual = np.asarray(mmm.holdout_id)
        np.testing.assert_array_equal(actual, expected)
        result['resolved_holdout_count'] = int(actual.sum())
    return result
