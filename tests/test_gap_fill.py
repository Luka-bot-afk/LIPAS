"""LIPAS."""
import numpy as np
import pandas as pd

from gap_fill import (
    cross_fill_omni_drivers,
    expand_base_to_omni_spine,
    f107_from_ssn,
    gap_fill_extended_training,
    interpolate_numeric_columns,
    kp_from_ap,
)

def test_kp_ap_roundtrip_reasonable():
    assert 3.5 <= kp_from_ap(27) <= 4.5
    assert f107_from_ssn(100) > 100

def test_cross_fill_from_siblings():
    df = pd.DataFrame([{
        'kp_index': np.nan, 'ap': 27.0, 'f107': np.nan, 'ssn': 100.0,
        'solar_wind_speed': np.nan, 'solar_wind_density': np.nan, 'imf_bz': np.nan,
    }])
    out = cross_fill_omni_drivers(df)
    assert pd.notna(out.loc[0, 'kp_index'])
    assert pd.notna(out.loc[0, 'f107'])
    assert abs(float(out.loc[0, 'solar_wind_speed']) - 400.0) < 1e-6

def test_expand_spine_is_noop():
    base = pd.DataFrame({'date': ['2020-01-01'], 'solar_activity': [5.0]})
    omni = pd.DataFrame({'date': ['2020-01-01', '2020-01-02'], 'kp_index': [2.0, 3.0]})
    assert len(expand_base_to_omni_spine(base, omni)) == 1

def test_gap_fill_does_not_invent_targets():
    df = pd.DataFrame({
        'date': ['2020-01-01', '2020-01-02'],
        'site': ['A', 'A'],
        'solar_activity': [5.0, 6.0],
        'radiation_mSv': [0.05, 0.06],
        'temperature_C': [-100.0, -90.0],
        'moonquakes_per_day': [40.0, 41.0],
        'meteor_flux_1e15': [1.6, 1.7],
        'dust_g_cm3': [1.5, 1.6],
        'lat': [0.0, 0.0], 'lon': [0.0, 0.0],
        'local_solar_time': [12.0, 13.0],
        'hour_of_day': [12.0, 13.0],
        'day_of_month': [1.0, 2.0],
        'month_of_year': [1.0, 1.0],
        'solar_wind_speed': [400.0, np.nan],
        'solar_wind_density': [5.0, 5.0],
        'imf_bz': [-2.0, -2.0],
        'kp_index': [2.0, 2.0],
        'regolith_depth': [4.0, 4.0],
        'thermal_inertia': [50.0, 50.0],
        'target_solar_activity': [5.0, np.nan],
        'target_radiation_mSv': [0.05, 0.06],
        'target_temperature_C': [-100.0, -90.0],
        'target_moonquakes_per_day': [40.0, 41.0],
        'target_meteor_flux_1e15': [1.6, 1.7],
        'target_dust_g_cm3': [1.5, 1.6],
    })
    out = gap_fill_extended_training(df)
    assert len(out) == 1
    assert out.iloc[0]['date'] == '2020-01-01'

def test_short_interp_drivers():
    df = pd.DataFrame({
        'date': ['2020-01-01', '2020-01-02', '2020-01-03'],
        'kp_index': [2.0, np.nan, 4.0],
    })
    out = interpolate_numeric_columns(df, ['kp_index'], limit=5)
    assert abs(float(out.loc[1, 'kp_index']) - 3.0) < 1e-6
