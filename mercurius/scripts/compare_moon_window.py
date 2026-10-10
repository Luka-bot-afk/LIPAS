"""Compare Moon vs Mercury on the same 1 AU drivers. Prints retrain verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lunar_physics import physics_radiation, physics_solar_activity, physics_temperature
from mercurius.mercury_model import RETRAIN_VERDICT, hybrid_forecast
from mercurius.mercury_physics import mercury_r_au, physics_estimate_mercury

def main():
    extra = {
        'kp_index': 4.0,
        'imf_bz': -5.0,
        'solar_wind_speed': 450.0,
        'solar_wind_density': 6.0,
        'f107': 140.0,
        'proton_flux': 0.2,
    }
    r = mercury_r_au()
    extra['r_au'] = r
    inputs = [8.0, 0.07, 0.0, 0.0, 0.0, 0.0]
    moon_t = physics_temperature(0.0, 0.0, 12.0)
    moon_rad = physics_radiation(8.0, 4.0, 0.2, lat=0.0, imf_bz=-5.0, solar_wind_speed=450.0)
    moon_sol = physics_solar_activity(8.0, 4.0, -5.0, 450.0, 6.0, f107=140.0)
    merc = physics_estimate_mercury(inputs, lat=0.0, lon=0.0, local_time=12.0, extra=extra)
    print(f'r_AU={r:.4f}')
    print(f'{"chan":12} {"Moon":>10} {"Mercury":>10}')
    print(f'{"solar":12} {moon_sol:10.2f} {merc["solar"]:10.2f}')
    print(f'{"radiation":12} {moon_rad:10.4f} {merc["radiation"]:10.4f}')
    print(f'{"temp_C":12} {moon_t:10.1f} {merc["temperature"]:10.1f}')
    print(f'MP standoff {merc["magnetopause_rm"]:.2f} R_M  Pdyn {merc["p_dyn_npa"]:.2f} nPa')
    print('--- retrain verdict ---')
    print(json.dumps(RETRAIN_VERDICT, indent=2))
    if merc['temperature'] > 130:
        print('Lunar LSTM temperature cap (130 C) cannot represent Mercury dayside.')
    out = ROOT / 'mercurius' / 'data' / 'retrain_verdict.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        'r_au': r,
        'moon': {'solar': moon_sol, 'radiation': moon_rad, 'temperature': moon_t},
        'mercury': {
            'solar': merc['solar'], 'radiation': merc['radiation'],
            'temperature': merc['temperature'], 'magnetopause_rm': merc['magnetopause_rm'],
        },
        'verdict': RETRAIN_VERDICT,
    }, indent=2), encoding='utf-8')
    print(f'wrote {out}')

if __name__ == '__main__':
    main()
