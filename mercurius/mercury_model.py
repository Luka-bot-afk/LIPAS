from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mercurius.mercury_physics import physics_estimate_mercury

PARENT_MODEL_DIR = str(_ROOT / 'saved_model')
MERCURY_MODEL_DIR = str(_ROOT / 'mercurius' / 'saved_model')

RETRAIN_VERDICT = {
    'retrain_lunar_lstm': False,
    'use_lunar_weights_on_mercury_outputs': False,
    'adapt_train2_architecture': True,
    'mercury_lstm_dir': 'mercurius/saved_model',
    'use_1au_heliospheric_drivers': True,
    'reasons': [
        'Lunar PhysicalBoundsLayer caps temperature at 130 °C; Mercury dayside is physics-only, not LSTM.',
        'Lunar radiation labels are unshielded-Moon GCR/SEP, not Hermean magnetosphere attenuation.',
        'Moonquake, dust, and micrometeorite channels have no Mercury counterpart in this model.',
        'Heliospheric OMNI/SWPC/GOES drivers are the same 1 AU series — reuse as LSTM inputs.',
        'Train a Mercury-headed LSTM (train2 window/arch, next-day Y) into mercurius/saved_model, not a lunar fine-tune.',
    ],
}

def one_au_solar_prior(inputs, extra=None) -> tuple[float, bool, str]:
    extra = extra or {}
    solar_in = float(inputs[0]) if inputs else 5.0
    try:
        from lunar_physics import physics_solar_activity
        solar = physics_solar_activity(
            solar_activity=solar_in,
            kp=float(extra.get('kp_index', 3.0)),
            imf_bz=float(extra.get('imf_bz', -2.0)),
            solar_wind_speed=float(extra.get('solar_wind_speed', 400.0)),
            solar_wind_density=float(extra.get('solar_wind_density', 5.0)),
            f107=extra.get('f107'),
        )
        return float(solar), False, 'lipas_physics_solar_1au'
    except Exception:
        return solar_in, False, 'input_solar'

def hybrid_forecast(inputs, lat=0.0, lon=0.0, local_time=12.0, extra=None) -> dict[str, Any]:
    extra = dict(extra or {})
    solar_1au, _, src = one_au_solar_prior(inputs, extra)
    use_inputs = list(inputs) if inputs else [solar_1au, 0.06, 0.0, 0.0, 0.0, 0.0]
    if len(use_inputs) < 6:
        use_inputs = (use_inputs + [0.0] * 6)[:6]
    use_inputs[0] = solar_1au
    phys = physics_estimate_mercury(
        use_inputs, lat=lat, lon=lon, local_time=local_time,
        day_of_year=extra.get('day_of_year'), extra=extra,
    )
    from mercurius.mercury_lstm import blend_with_physics, model_ready, predict_channels

    ml = None
    ml_used = False
    ml_error = None
    ml_ready = bool(model_ready())
    try:
        if ml_ready and not extra.get('skip_ml'):
            ml = predict_channels(phys, lat=lat, lon=lon, lst=local_time, extra=extra)
            ml_used = ml is not None
        elif not ml_ready:
            ml_error = 'no_weights'
    except Exception as exc:
        ml = None
        ml_used = False
        ml_error = type(exc).__name__

    if ml_used:
        hybrid = blend_with_physics(phys, ml)
        source = 'mercury_lstm+physics'
    else:
        hybrid = blend_with_physics(phys, None)
        source = 'mercury_physics+1au_solar_prior'

    return {
        'hybrid': hybrid,
        'physics': phys,
        'ml': ml,
        'solar_prior_1au': solar_1au,
        'solar_prior_source': src,
        'solar_prior_used_lstm': ml_used,
        'ml_ready': ml_ready,
        'ml_error': ml_error,
        'blend_policy': RETRAIN_VERDICT,
        'source': source,
    }
