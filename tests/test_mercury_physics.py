import math
import unittest
from datetime import datetime, timezone

from mercurius.mercury_magnetosphere import (
    bow_shock_standoff_rm,
    classify_equatorial,
    classify_point,
    magnetopause_standoff_rm,
    magnetosphere_state,
)
from mercurius.mercury_lstm import (
    OUTPUT_BOUNDS,
    CHANNEL_KEYS,
    attach_next_day_targets,
    blend_with_physics,
    feature_vector,
    mercury_storm_sample_weights,
    mix_heads_on_val,
    persistence_rmse,
)
from mercurius.mercury_model import RETRAIN_VERDICT, hybrid_forecast
from mercurius.mercury_physics import (
    dynamic_pressure_npa,
    earth_lead_time_hours,
    kepler_eccentric_anomaly,
    mercury_r_au_kepler,
    physics_estimate_mercury,
    physics_radiation_mercury,
    physics_temperature_mercury,
    scale_solar_wind_to_mercury,
    solar_constant_mercury,
    MERCURY_APHELION_AU,
    MERCURY_PERIHELION_AU,
)
from mercurius.mercury_sites import SITES, get_site

class TestMercuryOrbit(unittest.TestCase):
    def test_kepler_circular(self):
        self.assertAlmostEqual(kepler_eccentric_anomaly(0.3, 0.0), 0.3, places=12)

    def test_r_au_in_mercury_range(self):
        r = mercury_r_au_kepler(datetime(2026, 7, 12, tzinfo=timezone.utc))
        self.assertGreater(r, MERCURY_PERIHELION_AU * 0.99)
        self.assertLess(r, MERCURY_APHELION_AU * 1.01)

    def test_solar_constant_scales_r2(self):
        s1 = solar_constant_mercury(1.0)
        s_m = solar_constant_mercury(0.387)
        self.assertAlmostEqual(s1, 1361.0, places=0)
        self.assertGreater(s_m / s1, 6.0)
        self.assertLess(s_m / s1, 7.2)

class TestSolarWindScaling(unittest.TestCase):
    def test_density_r2_not_b_dipole(self):
        sw = scale_solar_wind_to_mercury(400.0, 5.0, -4.0, 0.387)
        self.assertAlmostEqual(sw['density'], 5.0 / (0.387 ** 2), places=4)
        self.assertEqual(sw['speed'], 400.0)

        self.assertAlmostEqual(sw['imf_bz'], -4.0 / 0.387, places=3)
        self.assertLess(abs(sw['imf_bz']), 20.0)
        self.assertGreater(sw['imf_b_mag'], abs(sw['imf_bz']) * 0.9)

    def test_dynamic_pressure(self):
        p1 = dynamic_pressure_npa(5.0, 400.0)
        p_m = dynamic_pressure_npa(5.0 / (0.387 ** 2), 400.0)
        self.assertGreater(p1, 1.0)
        self.assertLess(p1, 2.0)
        self.assertGreater(p_m / p1, 6.0)

class TestMagnetosphere(unittest.TestCase):
    def test_quiet_standoff_near_messenger_mean(self):
        p = dynamic_pressure_npa(5.0 / (0.387 ** 2), 400.0)
        rss = magnetopause_standoff_rm(p)
        self.assertGreater(rss, 1.25)
        self.assertLess(rss, 1.70)
        self.assertGreater(bow_shock_standoff_rm(rss), rss)

    def test_storm_can_reach_surface(self):
        rss = magnetopause_standoff_rm(80.0)
        self.assertLess(rss, 1.15)

    def test_regions(self):
        rss = 1.45
        self.assertEqual(classify_point(0.0, 0.0, rss), 'planet')
        self.assertEqual(classify_point(2.8, 0.0, rss), 'solar_wind')
        self.assertIn(classify_point(1.6, 0.2, rss), ('magnetosheath', 'solar_wind', 'magnetosphere'))

    def test_state_has_draw_payload(self):
        st = magnetosphere_state(10.0, -8.0, -12.0, 25.0)
        self.assertIn('grid', st)
        self.assertIn('equatorial_grid', st)
        self.assertIn('bmag_grid', st)
        self.assertIn('field_lines', st)
        self.assertIn('magnetopause', st)
        self.assertEqual(st['imf_clock']['orientation'], 'southward')
        self.assertEqual(classify_equatorial(0.0, 0.0, 1.45), 'planet')
        self.assertEqual(classify_equatorial(2.8, 0.0, 1.45), 'solar_wind')

class TestThermalRadiation(unittest.TestCase):
    def test_dayside_hotter_than_moon_bounds(self):
        t = physics_temperature_mercury(0.0, 0.0, 12.0, r_au=0.307)
        self.assertGreater(t, 130.0)
        self.assertLess(t, 460.0)

    def test_nightside_cold_not_geothermal_only(self):
        t = physics_temperature_mercury(0.0, 0.0, 2.0, r_au=0.387)
        self.assertLess(t, -100.0)
        self.assertGreater(t, -200.0)

    def test_gcr_lower_sep_higher_at_mercury(self):
        rad_quiet = physics_radiation_mercury(
            solar_activity=5.0, kp=2.0, proton_flux=0.05, r_au=0.387, magnetopause_rm=1.45,
        )
        rad_sep = physics_radiation_mercury(
            solar_activity=20.0, kp=6.0, proton_flux=0.8, r_au=0.387, magnetopause_rm=1.05,
            local_time=12.0,
        )
        self.assertGreater(rad_sep, rad_quiet * 2.0)

    def test_lead_time_mercury_first(self):
        lead = earth_lead_time_hours(0.387, 400.0)
        self.assertGreater(lead['lead_time_h'], 30.0)
        self.assertGreater(lead['photon_lead_min'], 4.0)

    def test_estimate_bundle(self):
        extra = {
            'kp_index': 4.0, 'imf_bz': -6.0, 'solar_wind_speed': 500.0,
            'solar_wind_density': 8.0, 'r_au': 0.387, 'terrain': 'smooth_plains',
        }
        out = physics_estimate_mercury([10.0, 0.08], lat=0.0, lon=0.0, local_time=12.0, extra=extra)
        self.assertIn('magnetopause_rm', out)
        self.assertGreater(out['temperature'], 100.0)

class TestSites(unittest.TestCase):
    def test_six_sites(self):
        self.assertGreaterEqual(len(SITES), 12)
        self.assertGreater(abs(get_site('prokofiev').lat), 80.0)
        self.assertGreater(abs(get_site('chao').lat), 80.0)
        self.assertTrue(any(s.id == 'antipode' for s in SITES))
        lons = sorted(((s.lon + 360.0) % 360.0) for s in SITES if abs(s.lat) < 70)

        self.assertTrue(any(0 <= L < 90 for L in lons))
        self.assertTrue(any(90 <= L < 180 for L in lons))
        self.assertTrue(any(180 <= L < 270 for L in lons))
        self.assertTrue(any(270 <= L < 360 for L in lons))

class TestMercuryLstmPolicy(unittest.TestCase):
    def test_train2_not_reused_for_lunar_weights(self):
        self.assertFalse(RETRAIN_VERDICT['use_lunar_weights_on_mercury_outputs'])
        self.assertTrue(RETRAIN_VERDICT['adapt_train2_architecture'])
        self.assertEqual(RETRAIN_VERDICT['mercury_lstm_dir'], 'mercurius/saved_model')

    def test_mercury_output_bounds_are_solar_only(self):
        self.assertEqual(CHANNEL_KEYS, ('solar', 'radiation', 'standoff_rm', 'p_dyn_npa', 'imf_b_mag'))
        self.assertEqual(len(OUTPUT_BOUNDS), 5)
        self.assertNotIn('temperature', CHANNEL_KEYS)
        self.assertGreater(OUTPUT_BOUNDS[0][1], 50.0)

    def test_feature_vector_is_train2_width(self):
        extra = {
            'kp_index': 4.0, 'imf_bz': -6.0, 'solar_wind_speed': 500.0,
            'solar_wind_density': 8.0, 'r_au': 0.387, 'terrain': 'smooth_plains',
        }
        phys = physics_estimate_mercury([10.0, 0.08], lat=0.0, lon=0.0, local_time=12.0, extra=extra)
        vec = feature_vector(phys, 0.0, 0.0, 12.0, extra)
        self.assertEqual(vec.shape, (18,))

    def test_blend_without_ml_is_physics(self):
        extra = {
            'kp_index': 4.0, 'imf_bz': -6.0, 'solar_wind_speed': 500.0,
            'solar_wind_density': 8.0, 'r_au': 0.387,
        }
        phys = physics_estimate_mercury([10.0, 0.08], lat=0.0, lon=0.0, local_time=12.0, extra=extra)
        blended = blend_with_physics(phys, None)
        self.assertAlmostEqual(blended['solar'], phys['solar'])
        self.assertAlmostEqual(blended['radiation'], phys['radiation'])

    def test_next_day_targets_are_not_identity(self):
        import pandas as pd
        df = pd.DataFrame({
            'date': ['2020-01-01', '2020-01-02', '2020-01-03'] * 2,
            'site': ['equator'] * 3 + ['caloris'] * 3,
            'solar_activity': [10.0, 20.0, 30.0, 11.0, 21.0, 31.0],
            'radiation_mSv': [1.0, 2.0, 3.0, 1.1, 2.1, 3.1],
            'temperature_C': [100.0, 110.0, 120.0, 90.0, 95.0, 99.0],
            'moonquakes_per_day': [1.4, 1.3, 1.2, 1.45, 1.35, 1.25],
            'meteor_flux_1e15': [10.0, 20.0, 40.0, 11.0, 22.0, 33.0],
            'dust_g_cm3': [30.0, 40.0, 50.0, 31.0, 41.0, 51.0],
            'target_solar_activity': [10.0, 20.0, 30.0, 11.0, 21.0, 31.0],
            'target_radiation_mSv': [1.0, 2.0, 3.0, 1.1, 2.1, 3.1],
            'target_temperature_C': [100.0, 110.0, 120.0, 90.0, 95.0, 99.0],
            'target_moonquakes_per_day': [1.4, 1.3, 1.2, 1.45, 1.35, 1.25],
            'target_meteor_flux_1e15': [10.0, 20.0, 40.0, 11.0, 22.0, 33.0],
            'target_dust_g_cm3': [30.0, 40.0, 50.0, 31.0, 41.0, 51.0],
        })
        same = persistence_rmse(df)
        nxt = attach_next_day_targets(df, horizon=1)
        self.assertGreater(same, -1e-12)
        self.assertLess(same, 1e-9)
        self.assertEqual(len(nxt), 4)
        self.assertGreater(persistence_rmse(nxt), 5.0)
        eq = nxt[nxt['site'] == 'equator'].iloc[0]
        self.assertAlmostEqual(eq['solar_activity'], 10.0)
        self.assertAlmostEqual(eq['target_solar_activity'], 20.0)

    def test_mercury_storm_weights_not_lunar(self):
        import numpy as np
        Y = np.array([
            [8.0, 1.0, 1.45, 8.0, 20.0],
            [40.0, 6.0, 1.05, 90.0, 120.0],
        ], dtype=np.float64)
        w = mercury_storm_sample_weights(Y)
        self.assertGreater(w[1], w[0])
        self.assertGreater(w[1], 2.0)

    def test_channel_mix_picks_better_head(self):
        import numpy as np
        y = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]], dtype=np.float64)
        persist = y + 2.0
        lstm = np.column_stack([y[:, 0] + 0.1, y[:, 1] + 2.0])
        ridge = np.column_stack([y[:, 0] + 2.0, y[:, 1] + 0.1])
        mix = mix_heads_on_val(lstm, ridge, persist, y)
        self.assertGreater(mix[0]['lstm'], mix[0]['ridge'])
        self.assertGreater(mix[1]['ridge'], mix[1]['lstm'])

    def test_southward_bz_compresses_standoff(self):
        p = 10.0
        quiet = magnetopause_standoff_rm(p)
        south = magnetopause_standoff_rm(p, imf_bz_nt=-40.0)
        north = magnetopause_standoff_rm(p, imf_bz_nt=40.0)
        self.assertLess(south, quiet)
        self.assertGreater(north, quiet)
        self.assertGreater(south, 0.82)

    def test_history_warm_starts_full_window(self):
        import numpy as np
        from mercurius.mercury_lstm import SEQUENCE_LENGTH, _HISTORY, _push_history
        _HISTORY.clear()
        window = _push_history(1.0, 2.0, np.ones(18, dtype=np.float32))
        self.assertEqual(window.shape, (SEQUENCE_LENGTH, 18))
        self.assertEqual(len(_HISTORY['1.00,2.00']), SEQUENCE_LENGTH)

    def test_unknown_dataset_site_is_rejected(self):
        from mercurius.mercury_sites import require_site
        with self.assertRaises(KeyError):
            require_site('rembrandt')

    def test_hybrid_does_not_load_lunar_saved_model(self):
        extra = {
            'kp_index': 3.0, 'imf_bz': -2.0, 'solar_wind_speed': 400.0,
            'solar_wind_density': 5.0, 'r_au': 0.387, 'skip_ml': True,
        }
        out = hybrid_forecast([8.0, 0.06], lat=0.0, lon=0.0, local_time=12.0, extra=extra)
        self.assertIn(out['source'], ('mercury_physics+1au_solar_prior', 'mercury_lstm+physics'))
        self.assertNotIn('saved_model/', out['source'])
        self.assertIn('temperature', out['hybrid'])
        self.assertGreater(out['hybrid']['temperature'], -250.0)
        self.assertIn('standoff_rm', out['hybrid'])
        self.assertNotIn('temperature', CHANNEL_KEYS)

class TestTerrainAndNowcast(unittest.TestCase):
    def test_known_site_terrains_are_not_generic(self):
        t_plain = physics_temperature_mercury(0.0, 0.0, 12.0, r_au=0.387, terrain='smooth_plains')
        t_ray = physics_temperature_mercury(0.0, 0.0, 12.0, r_au=0.387, terrain='ray_crater')
        t_chaos = physics_temperature_mercury(-30.0, -18.5, 12.0, r_au=0.387, terrain='chaotic')
        self.assertLess(t_ray, t_plain)
        self.assertTrue(math.isfinite(t_chaos))

    def test_sunrise_thermal_lag(self):
        noon = physics_temperature_mercury(0.0, 0.0, 12.0, r_au=0.387)
        dawn = physics_temperature_mercury(0.0, 0.0, 6.4, r_au=0.387)
        self.assertGreater(noon, 130.0)
        self.assertLess(dawn, noon - 40.0)

    def test_imf_magnitude_uses_measured_bt(self):
        sw_bt = scale_solar_wind_to_mercury(400.0, 5.0, -5.0, 0.387, imf_bt_1au=6.0)
        sw_bz = scale_solar_wind_to_mercury(400.0, 5.0, -5.0, 0.387)

        self.assertLess(sw_bt['imf_b_mag'], sw_bz['imf_b_mag'] * 1.15)
        self.assertGreater(sw_bt['imf_b_mag'], abs(sw_bt['imf_bz']) * 0.9)

    def test_goes_class_and_location(self):
        from swpc_nowcast import flare_class_from_flux, parse_swpc_location, interp_series, drivers_at_hour
        cls, idx = flare_class_from_flux(2.3e-5)
        self.assertTrue(cls.startswith('M'))
        self.assertGreater(idx, 3.0)
        lat, lon = parse_swpc_location('S11E36', -11, 36)
        self.assertAlmostEqual(lat, -11.0)
        self.assertAlmostEqual(lon, -36.0)
        y = interp_series([(-2.0, 1.0), (0.0, 3.0)], -1.0)
        self.assertAlmostEqual(y, 2.0, places=5)
        extra = {
            'kp_index': 3.0, 'imf_bz': -4.0, 'solar_wind_speed': 420.0,
            'solar_wind_density': 6.0, 'flare_index': 3.0, 'xray_flux': 1e-6,
            'series': {
                'kp': [(-1.0, 3.0), (0.0, 3.0), (3.0, 4.0)],
                'kp_forecast': [(6.0, 5.0), (12.0, 4.0)],
                'xray_flux': [(-1.0, 1e-6), (0.0, 1e-6)],
            },
        }
        h0 = drivers_at_hour(extra, 0.0)
        h12 = drivers_at_hour(extra, 12.0)
        self.assertAlmostEqual(h0['kp_index'], 3.0, places=5)
        self.assertAlmostEqual(h12['kp_index'], 4.0, places=5)
        self.assertNotAlmostEqual(h12['kp_index'], 3.0 + 0.45 * math.sin(math.pi + 1.4), places=2)

    def test_hermean_surface_channels(self):
        from mercurius.serve import _hermean_surface
        noon = _hermean_surface({
            'lst_h': 12.0, 'r_au': 0.387,
            'prediction': {'radiation': 0.08, 'temperature': 350.0, 'solar': 20.0},
            'physics': {'kp_index': 4.0, 'flare_index': 3.0},
        }, 0.0)
        night = _hermean_surface({
            'lst_h': 2.0, 'r_au': 0.387,
            'prediction': {'radiation': 0.08, 'temperature': -160.0, 'solar': 20.0},
            'physics': {'kp_index': 4.0, 'flare_index': 3.0},
        }, 0.0)
        self.assertGreater(noon['dust'], night['dust'])
        self.assertGreater(noon['comms'], night['comms'])
        self.assertGreater(noon['micrometeorites'], 0.5)
        self.assertGreater(night['evaRisk'], 0.0)

if __name__ == '__main__':
    unittest.main()
