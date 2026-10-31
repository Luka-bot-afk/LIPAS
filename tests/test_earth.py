import unittest
from terra.earth_physics import geomagnetic_lat, g_scale, site_nowcast
from terra.earth_sites import SITES, get_site
from terra.satellites import propagate_elements
from datetime import datetime, timezone
class TestEarth(unittest.TestCase):
    def test_catalog_size(self):
        self.assertGreaterEqual(len(SITES), 30)
        self.assertEqual(get_site('ksc').name, 'Kennedy Space Center')
        self.assertEqual(get_site('starbase').name, 'Starbase / Boca Chica')
        self.assertEqual(get_site('overview').group, 'overview')
    def test_satellite_nowcast_keys(self):
        from terra.earth_physics import satellite_nowcast
        n = satellite_nowcast(-25.0, -50.0, 420.0, {'kp_index': 4.0, 'flare_index': 2.0, 'f107': 150})
        self.assertIn('saa', n)
        self.assertIn('drag', n)
        self.assertIn('charging', n)
    def test_mission_corridor(self):
        from terra.mission import plan_mission
        p = plan_mission({
            'from_id': 'starbase', 'to_id': 'ksc',
            'alt1_km': 0, 'alt2_km': 220, 'hours': 6, 't0_h': 0,
        })
        self.assertIn(p['status'], ('go', 'caution', 'nogo'))
        self.assertGreater(len(p['samples']), 8)
        self.assertIn('saa', p['hazard_matrix'])
    def test_mag_lat_fairbanks_high(self):
        m = geomagnetic_lat(65.13, -147.47)
        self.assertGreater(m, 55.0)
    def test_g_scale(self):
        self.assertEqual(g_scale(3), 'G0')
        self.assertEqual(g_scale(5), 'G1')
        self.assertEqual(g_scale(8), 'G4')
    def test_nowcast_keys(self):
        n = site_nowcast(40.0, -105.0, {'kp_index': 4.0, 'flare_index': 2.0, 'imf_bz': -3.0})
        self.assertIn('aurora_pct', n)
        self.assertIn('aviation_usv_h', n)
        self.assertTrue(0 <= n['aurora_pct'] <= 100)
    def test_overview_is_planetwide(self):
        from terra.serve import _overview_nowcast
        extra = {'kp_index': 6.0, 'flare_index': 3.0, 'imf_bz': -6.0}
        when = datetime(2026, 8, 27, 6, tzinfo=timezone.utc)
        ov = _overview_nowcast(extra, when)
        boulder = site_nowcast(40.015, -105.27, extra, when)
        fairbanks = site_nowcast(64.838, -147.716, extra, when)
        tromso = site_nowcast(69.65, 18.96, extra, when)
        singapore = site_nowcast(1.35, 103.82, extra, when)
        self.assertNotEqual(ov['aurora_pct'], boulder['aurora_pct'])
        self.assertGreater(tromso['aurora_pct'], singapore['aurora_pct'])
        self.assertGreater(fairbanks['pca'], boulder['pca'])
        self.assertEqual(ov['day_night'], 'mixed')
    def test_location_forecasts_differ(self):
        extra = {'kp_index': 6.5, 'flare_index': 4.0, 'imf_bz': -8.0, 'proton_flux': 2.0}
        when = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
        fa = site_nowcast(64.838, -147.716, extra, when)
        ho = site_nowcast(21.31, -157.86, extra, when)
        self.assertGreater(fa['aurora_pct'], ho['aurora_pct'])
        self.assertGreater(fa['pca'], ho['pca'])
    def test_hour_shifts_lst_and_hf(self):
        extra = {'kp_index': 3.0, 'flare_index': 6.0, 'imf_bz': -2.0}
        day = datetime(2026, 8, 27, 17, tzinfo=timezone.utc)
        night = datetime(2026, 8, 27, 5, tzinfo=timezone.utc)
        ksc_day = site_nowcast(28.572, -80.649, extra, day)
        ksc_night = site_nowcast(28.572, -80.649, extra, night)
        self.assertNotEqual(ksc_day['lst_h'], ksc_night['lst_h'])
        self.assertGreater(ksc_day['hf_blackout'], ksc_night['hf_blackout'])
    def test_mission_vehicle_gto_altitude(self):
        from terra.mission import plan_mission
        p = plan_mission({
            'from_id': 'kourou', 'to_id': 'goes16',
            'vehicle': 'gto', 'hours': 6, 't0_h': 0,
        })
        self.assertGreater(p['peak_alt_km'], 10000)
        self.assertIn('drag', p['hazard_matrix'])
        self.assertIn('comms', p['hazard_matrix'])
        self.assertTrue(p['windows'])
        self.assertIn('best_window', p)
        self.assertTrue(any(s.get('phase') for s in p['samples']))
    def test_iss_catalog_filter(self):
        from terra.satellites import _wanted
        self.assertTrue(_wanted('ISS (ZARYA)'))
        self.assertFalse(_wanted('ISS (NAUKA)'))
        self.assertTrue(_wanted('GOES 16'))
        self.assertTrue(_wanted('TERRA'))
        self.assertFalse(_wanted('SKYTERRA 1'))
        self.assertTrue(_wanted('AQUA'))
    def test_iss_propagate(self):
        el = {
            'INCLINATION': 51.6, 'RA_OF_ASC_NODE': 10.0, 'ARG_OF_PERICENTER': 20.0,
            'MEAN_ANOMALY': 30.0, 'ECCENTRICITY': 0.0004, 'MEAN_MOTION': 15.5,
            'EPOCH': '2026-08-26T12:00:00',
        }
        pos = propagate_elements(el, datetime(2026, 8, 26, 14, tzinfo=timezone.utc))
        self.assertIsNotNone(pos)
        self.assertTrue(-90 <= pos['lat'] <= 90)
        self.assertGreater(pos['alt_km'], 300)
if __name__ == '__main__':
    unittest.main()
