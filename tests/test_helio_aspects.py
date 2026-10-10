import math
import unittest
from datetime import datetime, timedelta, timezone

from helio_aspects import (
    LUNAR_PHASE_REFERENCE,
    cosine_incidence,
    globe_clock,
    lunar_local_solar_time,
    lunar_phase_fraction,
    lunar_subsolar,
    planet_aspects,
    wrap_lon,
)
from mercurius.mercury_physics import local_solar_time_mercury, mercury_subsolar

class TestLunarSubsolar(unittest.TestCase):
    def test_new_moon_lights_far_side(self):
        sub = lunar_subsolar(LUNAR_PHASE_REFERENCE)
        self.assertGreater(abs(sub["lon"]), 170.0)
        self.assertAlmostEqual(lunar_phase_fraction(LUNAR_PHASE_REFERENCE), 0.0, places=2)

    def test_full_moon_lights_near_side(self):
        full = LUNAR_PHASE_REFERENCE + timedelta(days=29.530588853 / 2.0)
        sub = lunar_subsolar(full)
        self.assertLess(abs(sub["lon"]), 12.0)

    def test_near_side_noon_at_full_moon(self):
        full = LUNAR_PHASE_REFERENCE + timedelta(days=29.530588853 / 2.0)
        lst = lunar_local_solar_time(0.0, full)
        self.assertGreater(lst, 11.0)
        self.assertLess(lst, 13.0)

    def test_far_side_is_night_at_full_moon(self):
        full = LUNAR_PHASE_REFERENCE + timedelta(days=29.530588853 / 2.0)
        mu_near = cosine_incidence(0.0, 0.0, 0.0, lunar_subsolar(full)["lon"])
        mu_far = cosine_incidence(0.0, 180.0, 0.0, lunar_subsolar(full)["lon"])
        self.assertGreater(mu_near, 0.9)
        self.assertLess(mu_far, 0.05)

class TestPlanetAspects(unittest.TestCase):
    def test_earth_at_central_meridian(self):
        planets = {p["id"]: p for p in planet_aspects(datetime(2026, 8, 26, tzinfo=timezone.utc))}
        self.assertEqual(planets["earth"]["lon"], 0.0)
        self.assertTrue(planets["earth"]["earth_facing"])
        self.assertIn("jupiter", planets)
        self.assertLessEqual(abs(planets["jupiter"]["lon"]), 180.0)

class TestMercurySubsolar(unittest.TestCase):
    def test_noon_at_subsolar_longitude(self):
        when = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
        sub = mercury_subsolar(when)
        lst = local_solar_time_mercury(sub["lon"], when)
        self.assertAlmostEqual(lst, 12.0, places=2)
        self.assertLessEqual(abs(sub["lon"]), 180.0)

class TestGlobeClock(unittest.TestCase):
    def test_sun_clock_has_planets(self):
        clock = globe_clock("sun", hour=0.0, when=datetime(2026, 8, 26, 12, tzinfo=timezone.utc))
        names = [p["name"] for p in clock["planets"]]
        self.assertIn("Earth", names)
        self.assertIn("Jupiter", names)
        earth = next(p for p in clock["planets"] if p["id"] == "earth")
        self.assertEqual(earth["lon"], 0.0)

    def test_slider_advances_carrington(self):
        a = globe_clock("sun", hour=0.0, when=datetime(2026, 8, 26, 12, tzinfo=timezone.utc))
        b = globe_clock("sun", hour=24.0, when=datetime(2026, 8, 26, 12, tzinfo=timezone.utc))
        self.assertAlmostEqual(b["carrington_deg"] - a["carrington_deg"], 13.2, places=2)

    def test_moon_hour_moves_subsolar(self):
        when = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
        a = globe_clock("moon", hour=0.0, when=when)
        b = globe_clock("moon", hour=24.0, when=when)
        delta = abs(wrap_lon(b["subsolar"]["lon"] - a["subsolar"]["lon"]))
        self.assertGreater(delta, 10.0)
        self.assertLess(delta, 15.0)

if __name__ == "__main__":
    unittest.main()
