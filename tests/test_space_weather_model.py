import unittest
import json
from space_weather_model import app, plausibility_score, long_term_forecast
from data_ingestion import build_training_dataset

class TestSpaceWeatherModel(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_predict_fallback(self):
        payload = {'input': [5.0, 0.057, -160.0, 14.0, 1.6, 1.5]}
        response = self.client.post('/predict', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('prediction', data)
        self.assertIn('temperature', data['prediction'])

    def test_build_training_dataset_minimal(self):
        result = build_training_dataset(
            donki=[{'eventTime': '2026-06-27T12:00:00Z', 'classType': 'X1.0'}],
            noaa=[{'time_tag': '2026-06-27T00:00:00Z', 'flux': 12.3, 'kp': 4}],
            diviner=[{'date': '2026-06-27', 'temperature_C': -160.0}],
            apollo=[{'date': '2026-06-27', 'magnitude': 3.2}],
            mem3=[{'date': '2026-06-27', 'flux': 1.8}],
            ldex=[{'date': '2026-06-27', 'density': 1.6e-15}]
        )
        self.assertEqual(result.shape[0], 1)
        expected = [
            'solar_activity', 'radiation_mSv', 'temperature_C', 'moonquakes_per_day',
            'meteor_flux_1e15', 'dust_g_cm3', 'target_solar_activity', 'target_radiation_mSv',
            'target_temperature_C', 'target_moonquakes_per_day', 'target_meteor_flux_1e15', 'target_dust_g_cm3'
        ]

        cols = [c for c in result.columns if c != 'date']
        self.assertListEqual(cols, expected)
        self.assertIn('date', result.columns)

    def test_build_training_dataset_next_day_targets(self):
        result = build_training_dataset(
            donki=[
                {'eventTime': '2026-06-27T12:00:00Z', 'classType': 'X1.0'},
                {'eventTime': '2026-06-28T12:00:00Z', 'classType': 'M1.0'}
            ],
            noaa=[
                {'time_tag': '2026-06-27T00:00:00Z', 'flux': 12.3, 'kp': 4},
                {'time_tag': '2026-06-28T00:00:00Z', 'flux': 8.5, 'kp': 2}
            ],
            diviner=[
                {'date': '2026-06-27', 'temperature_C': -160.0},
                {'date': '2026-06-28', 'temperature_C': -150.0}
            ],
            apollo=[
                {'date': '2026-06-27', 'magnitude': 3.2},
                {'date': '2026-06-28', 'magnitude': 4.0}
            ],
            mem3=[
                {'date': '2026-06-27', 'flux': 1.8},
                {'date': '2026-06-28', 'flux': 1.7}
            ],
            ldex=[
                {'date': '2026-06-27', 'density': 1.6e-15},
                {'date': '2026-06-28', 'density': 1.7e-15}
            ]
        )
        self.assertEqual(result.shape[0], 2)
        self.assertAlmostEqual(result['target_radiation_mSv'].iloc[0], result['radiation_mSv'].iloc[1], places=3)
        self.assertAlmostEqual(result['target_temperature_C'].iloc[0], result['temperature_C'].iloc[1], places=3)

    def test_build_training_dataset_from_remote_payloads(self):
        result = build_training_dataset(
            donki={'sep': [{'eventTime': '2026-06-27T12:00:00Z', 'classType': 'X1.0'}]},
            noaa={
                'kp': [{'time_tag': '2026-06-27T00:00:00Z', 'kp': 4}],
                'flux': [{'time_tag': '2026-06-27T00:00:00Z', 'flux': 12.3}]
            },
            diviner=[{'date': '2026-06-27', 'temperature_C': -160.0}],
            apollo=[{'date': '2026-06-27', 'magnitude': 3.2}],
            mem3=[{'date': '2026-06-27', 'flux': 1.8}],
            ldex=[{'date': '2026-06-27', 'density': 1.6e-15}]
        )
        self.assertEqual(result.shape[0], 1)
        self.assertGreaterEqual(result['solar_activity'].iloc[0], 5.0)

    def test_build_training_dataset_with_crater(self):
        result = build_training_dataset(
            donki=[{'eventTime': '2026-06-27T12:00:00Z', 'classType': 'X1.0'}],
            noaa=[{'time_tag': '2026-06-27T00:00:00Z', 'flux': 12.3, 'kp': 4}],
            diviner=[{'date': '2026-06-27', 'temperature_C': -160.0}],
            crater=[{'date': '2026-06-27', 'radiation_mSv': 0.08}],
            apollo=[{'date': '2026-06-27', 'magnitude': 3.2}],
            mem3=[{'date': '2026-06-27', 'flux': 1.8}],
            ldex=[{'date': '2026-06-27', 'density': 1.6e-15}]
        )
        self.assertEqual(result.shape[0], 1)
        self.assertAlmostEqual(result['radiation_mSv'].iloc[0], 0.08, places=3)

    def test_long_term_forecast(self):
        forecast = long_term_forecast([5.0, 0.057, -160.0, 14.0, 1.6, 1.5], horizon=3, local_time=12.0)
        self.assertIn('long_term', forecast)
        self.assertEqual(len(forecast['long_term']), 3)
        for day in forecast['long_term']:
            self.assertIn('forecast', day)
            self.assertIn('plausibility', day)
            self.assertGreaterEqual(day['plausibility'], 0.0)
            self.assertLessEqual(day['plausibility'], 1.0)

    def test_plausibility_score(self):
        score = plausibility_score({'temperature': -160.0, 'radiation': 0.06}, [5.0, 0.057, -160.0, 14.0, 1.6, 1.5], lat=0.0, lon=0.0, local_time=0.0)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

if __name__ == '__main__':
    unittest.main()
