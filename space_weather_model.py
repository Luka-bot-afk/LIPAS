"""LIPAS."""
import os

# load .env if present

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import time
import json
import threading
import collections
import requests
import numpy as np

os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '1')
os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, regularizers, optimizers
    try:
        tf.config.threading.set_intra_op_parallelism_threads(1)
        tf.config.threading.set_inter_op_parallelism_threads(1)
    except RuntimeError:

        pass
    TF_AVAILABLE = True
except Exception:
    tf = None
    layers = models = regularizers = optimizers = None
    TF_AVAILABLE = False
from flask import Flask, request, jsonify
from data_ingestion import get_training_columns, get_schema_example, load_training_csv, build_training_dataset, save_dataset, batch_ingest_from_sources, fetch_real_source_data
from models import load_ensemble, ensemble_predict, train_ensemble
from functools import wraps

from lunar_physics import (
    SIGMA_SB,
    SOLAR_CONSTANT_W_M2,
    APOLLO_GEOTHERMAL_FLOOR_C,
    clamp,
    apollo_nightside_temperature,
    physics_temperature,
    physics_radiation,
    physics_micrometeorite_flux,
    physics_dust,
    physics_moonquake_rate,
    physics_solar_activity,
    calc_gcr_radiation,
    detect_storm_regime,
)

TRAINING_API_KEY = os.environ.get('TRAINING_API_KEY')

def require_api_key(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        key = TRAINING_API_KEY
        if not key:
            return jsonify({'error':'server misconfigured: TRAINING_API_KEY not set'}), 500
        header = request.headers.get('X-API-KEY') or request.args.get('api_key')
        if header != key:
            return jsonify({'error':'unauthorized'}), 401
        return f(*args, **kwargs)
    return wrapped

CONFIG = {
    'NASA_KEY': os.environ.get('NASA_KEY', 'DEMO_KEY'),
    'RADIATION_APIS': {
        'INTEGRAL': 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json',
        'DIFFERENTIAL': 'https://services.swpc.noaa.gov/json/goes/primary/differential-protons-1-day.json',
        'ELECTRONS': 'https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-1-day.json',
        'XRAY_PRI': 'https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json',
        'XRAY_SEC': 'https://services.swpc.noaa.gov/json/goes/secondary/xrays-1-day.json'
    }
}

DEFAULT_ML_BLEND_WEIGHT = 0.6
PHYSICS_WEIGHT_LOCKED = True
_CHANNEL_ML_BLEND_WEIGHTS = None

MODEL_DIR = 'saved_model'
MODEL_FILE = os.path.join(MODEL_DIR, 'model.keras')
BEST_MODEL_FILE = os.path.join(MODEL_DIR, 'best.keras')
ENSEMBLE_DIR = os.path.join(MODEL_DIR, 'ensemble')
CALIBRATION_NPZ_FILE = os.path.join(MODEL_DIR, 'calibration.npz')
CALIBRATION_PKL_FILE = os.path.join(MODEL_DIR, 'calibration.pkl')
BLEND_WEIGHTS_FILE = os.path.join(MODEL_DIR, 'blend_weights.npy')

CORE_FEATURE_NAMES = [
    'solar_activity', 'radiation_mSv', 'temperature_C',
    'moonquakes_per_day', 'meteor_flux_1e15', 'dust_g_cm3'
]
EXPANDED_FEATURE_NAMES = CORE_FEATURE_NAMES + [
    'lat', 'lon', 'local_solar_time',
    'hour_of_day', 'day_of_month', 'month_of_year',
    'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index',
    'regolith_depth', 'thermal_inertia'
]
NUM_CORE_FEATURES = len(CORE_FEATURE_NAMES)
NUM_EXPANDED_FEATURES = len(EXPANDED_FEATURE_NAMES)
SEQUENCE_LENGTH = 72  # hours for lstm window

PHYSICAL_OUTPUT_BOUNDS = [
    (0.0, 150.0),
    (0.0, 10.0),
    (-250.0, 130.0),
    (0.0, 100.0),
    (0.5, 8.0),
    (0.3, 6.0),
]

DEFAULT_TEMPORAL_HYPERPARAMS = {
    'lstm_units': (256, 128, 64),
    'dense_units': (256, 128),
    'dropout': (0.3, 0.25, 0.2, 0.3, 0.25),
    'l2_reg': 1e-4,
    'learning_rate': 1e-3,
    'use_attention': False,
    'use_last_timestep_skip': False,
}

if TF_AVAILABLE:
    @tf.keras.utils.register_keras_serializable(package='lipas')
    class PhysicalBoundsLayer(layers.Layer):
        def __init__(self, bounds, **kwargs):
            super().__init__(**kwargs)
            self.bounds = [(float(lo), float(hi)) for lo, hi in bounds]

        def build(self, input_shape):
            self.lo = tf.constant([b[0] for b in self.bounds], dtype=tf.float32)
            self.span = tf.constant([b[1] - b[0] for b in self.bounds], dtype=tf.float32)
            super().build(input_shape)

        def call(self, inputs):
            return self.lo + self.span * tf.sigmoid(inputs)

        def get_config(self):
            config = super().get_config()
            config.update({'bounds': self.bounds})
            return config

    @tf.keras.utils.register_keras_serializable(package='lipas')
    class WeightedSum1D(layers.Layer):
        def call(self, inputs):
            return tf.reduce_sum(inputs, axis=1)

        def compute_output_shape(self, input_shape):
            return (input_shape[0], input_shape[2])
else:
    PhysicalBoundsLayer = None
    WeightedSum1D = None

def _bounded_output_layer(x, name='bounded_output', bounds=None):
    bounds = bounds or PHYSICAL_OUTPUT_BOUNDS
    raw = layers.Dense(len(bounds), activation=None, name=f'{name}_raw')(x)
    return PhysicalBoundsLayer(bounds, name=name)(raw)

def build_model(input_shape=(18,), physical_bounds=False, learning_rate=1e-3):
    """Dense model for the core features."""
    inp = layers.Input(shape=input_shape)

    x = layers.BatchNormalization()(inp)

    if len(input_shape) == 2:

        seq_length = input_shape[0]
        num_features = input_shape[1]
    else:

        x = layers.Reshape((1, input_shape[0]))(x)
        seq_length = 1
        num_features = input_shape[0]

    x = layers.LSTM(128, return_sequences=True, kernel_regularizer=regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)

    x = layers.LSTM(64, return_sequences=False, kernel_regularizer=regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.25)(x)

    x = layers.Dense(256, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)

    x = layers.Dense(128, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.25)(x)

    nowcast = layers.Dense(64, activation='relu', kernel_regularizer=regularizers.l2(1e-4))(x)
    nowcast = layers.Dense(6, activation='linear', name='nowcast')(nowcast)

    forecast = layers.Dense(64, activation='relu', kernel_regularizer=regularizers.l2(1e-4))(x)
    forecast = layers.Dense(6, activation='linear', name='forecast')(forecast)

    combined = layers.Concatenate()([nowcast, forecast])
    if physical_bounds:
        calibrated = _bounded_output_layer(combined, name='calibrated')
    else:
        calibrated = layers.Dense(6, activation='linear', name='calibrated')(combined)

    model = models.Model(inputs=inp, outputs=calibrated)
    model.compile(
        optimizer=optimizers.Adam(learning_rate=learning_rate),
        loss='huber',
        metrics=['mae']
    )
    return model

def build_temporal_model(sequence_length=72, num_features=18, physical_bounds=False,
                          lstm_units=(256, 128, 64), dense_units=(256, 128),
                          dropout=(0.3, 0.25, 0.2, 0.3, 0.25), l2_reg=1e-4,
                          learning_rate=1e-3, use_attention=False,
                          use_last_timestep_skip=False, clipnorm=None):
\
\
\
\
\

    inp = layers.Input(shape=(sequence_length, num_features))

    x = layers.BatchNormalization(name='input_bn')(inp)

    if use_attention:
        gate = layers.Dense(num_features, activation='sigmoid', name='feature_gate',
                            kernel_regularizer=regularizers.l2(l2_reg))(x)
        x = layers.Multiply(name='gated_features')([x, gate])

    x = layers.LSTM(lstm_units[0], return_sequences=True, kernel_regularizer=regularizers.l2(l2_reg),
                    name='lstm_0')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[0])(x)

    x = layers.LSTM(lstm_units[1], return_sequences=True, kernel_regularizer=regularizers.l2(l2_reg),
                    name='lstm_1')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[1])(x)

    if use_attention:
        score = layers.Dense(1, activation=None, name='attn_score')(x)
        weights = layers.Softmax(axis=1, name='attn_weights')(score)
        weighted = layers.Multiply(name='attn_weighted')([x, weights])
        context = WeightedSum1D(name='attn_context')(weighted)
    else:
        context = None

    x = layers.LSTM(lstm_units[2], return_sequences=False, kernel_regularizer=regularizers.l2(l2_reg),
                    name='lstm_2')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[2])(x)

    if context is not None:
        x = layers.Concatenate(name='lstm_attn_concat')([x, context])

    if use_last_timestep_skip and sequence_length > 1:

        last = layers.Cropping1D(cropping=(sequence_length - 1, 0), name='last_timestep_crop')(inp)
        last = layers.Reshape((num_features,), name='last_timestep')(last)
        x = layers.Concatenate(name='last_skip_concat')([x, last])

    x = layers.Dense(dense_units[0], activation='relu', kernel_regularizer=regularizers.l2(l2_reg),
                     kernel_initializer='he_normal', name='dense_0')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[3])(x)

    x = layers.Dense(dense_units[1], activation='relu', kernel_regularizer=regularizers.l2(l2_reg),
                     kernel_initializer='he_normal', name='dense_1')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[4])(x)

    if physical_bounds:
        out = _bounded_output_layer(x, name='hazard_output')
    else:
        out = layers.Dense(6, activation='linear', name='hazard_output_linear')(x)

    model = models.Model(inputs=inp, outputs=out, name='lipas_temporal_hybrid')
    opt_kwargs = {'learning_rate': learning_rate}
    if clipnorm:
        opt_kwargs['clipnorm'] = float(clipnorm)
    model.compile(optimizer=optimizers.Adam(**opt_kwargs), loss='huber', metrics=['mae'])
    return model

def make_channel_normalized_huber(channel_scales, delta=1.0):
    if not TF_AVAILABLE or tf is None:
        return 'huber'
    scales = np.asarray(channel_scales, dtype=np.float32).reshape(-1)
    scales = np.maximum(scales, 1e-4)

    def loss_fn(y_true, y_pred):
        s = tf.constant(scales, dtype=y_true.dtype)
        err = (y_true - y_pred) / s
        abs_err = tf.abs(err)
        quad = tf.minimum(abs_err, delta)
        lin = abs_err - quad
        return tf.reduce_mean(0.5 * tf.square(quad) + delta * lin)

    loss_fn.__name__ = 'channel_normalized_huber'
    return loss_fn

def make_weighted_huber(channel_weights, delta=1.0):
    if not TF_AVAILABLE or tf is None:
        return 'huber'
    weights = np.asarray(channel_weights, dtype=np.float32).reshape(-1)
    weights = np.maximum(weights, 1e-6)

    def loss_fn(y_true, y_pred):
        w = tf.constant(weights, dtype=y_true.dtype)
        err = y_true - y_pred
        abs_err = tf.abs(err)
        quad = tf.minimum(abs_err, delta)
        lin = abs_err - quad
        per = 0.5 * tf.square(quad) + delta * lin
        return tf.reduce_mean(per * w)

    loss_fn.__name__ = 'weighted_huber'
    return loss_fn

def build_simple_model(physical_bounds=False):
    inp = layers.Input(shape=(6,))
    x = layers.Dense(128, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(inp)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.25)(x)
    x = layers.Dense(256, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(192, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.25)(x)
    x = layers.Dense(128, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(64, activation='relu')(x)
    x = layers.Dropout(0.15)(x)
    if physical_bounds:
        out = _bounded_output_layer(x, name='hazard_output')
    else:
        out = layers.Dense(6, activation='linear')(x)
    model = models.Model(inputs=inp, outputs=out)
    model.compile(optimizer=optimizers.Adam(learning_rate=1e-3), loss='huber', metrics=['mae'])
    return model

def _keras_custom_objects():
    objs = {}
    if PhysicalBoundsLayer is not None:
        objs['PhysicalBoundsLayer'] = PhysicalBoundsLayer
    if WeightedSum1D is not None:
        objs['WeightedSum1D'] = WeightedSum1D
    return objs

def load_saved_model(model_dir=MODEL_DIR, set_global=True):
    global _MODEL
    if not TF_AVAILABLE or tf is None:
        return None
    candidates = [
        os.path.join(model_dir, 'model.keras'),
        os.path.join(model_dir, 'best.keras'),
        os.path.join(model_dir, 'best.h5'),
        os.path.join(model_dir, 'model.h5'),
    ]
    custom = _keras_custom_objects()
    loaded = None
    for path in candidates:
        if os.path.exists(path):
            try:
                loaded = tf.keras.models.load_model(path, compile=False, custom_objects=custom)
                break
            except Exception as e:
                print(f'load_saved_model: failed to load {path}: {e}')
    if loaded is None and os.path.isdir(model_dir):
        try:
            loaded = tf.keras.models.load_model(model_dir, compile=False, custom_objects=custom)
        except Exception:
            pass
    if loaded is not None and set_global:
        _MODEL = loaded
    return loaded

def save_keras_model(model, model_dir=MODEL_DIR):
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'model.keras')
    model.save(model_path)
    try:
        model.save(os.path.join(model_dir, 'best.keras'))
    except Exception:
        pass
    try:
        model.save(os.path.join(model_dir, 'best.h5'))
    except Exception:
        pass
    return model_path

_MODEL = None
_MODEL_LOCK = threading.Lock()
_ENSEMBLE = []
_SCALER = None
_CALIBRATION = None
_LAST_TRAINING_METRICS = {}
_SURROGATE_COEFFS = None
_SURROGATE_INTERCEPT = None
_SURROGATE_LOCK = threading.Lock()

_FEATURE_HISTORY_BY_SITE = collections.OrderedDict()
_FEATURE_HISTORY_LOCK = threading.Lock()
_MAX_TRACKED_SITES = 256

def _site_key(lat, lon):
    try:
        return (round(float(lat), 2), round(float(lon), 2))
    except Exception:
        return (0.0, 0.0)

real_time_data = {'nasa': {}, 'noaa': {}, 'timestamp': 0}
historical_data = {}
radiation_cache = {'hourly': [], 'daily': [], 'timestamp': 0, 'raw': {}}

def safe_api(url, tag=None, timeout=10):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_donki(days=60):
    try:
        end = time.gmtime()
        e = time.strftime('%Y-%m-%d', end)
        start_ts = time.time() - days*24*3600
        s = time.strftime('%Y-%m-%d', time.gmtime(start_ts))
        key = CONFIG['NASA_KEY']
        base = 'https://api.nasa.gov/DONKI'
        sep = safe_api(f"{base}/SEP?startDate={s}&endDate={e}&api_key={key}", 'DONKI/SEP') or []
        flr = safe_api(f"{base}/FLR?startDate={s}&endDate={e}&api_key={key}", 'DONKI/FLR') or []
        cme = safe_api(f"{base}/CME?startDate={s}&endDate={e}&api_key={key}", 'DONKI/CME') or []
        gst = safe_api(f"{base}/GST?startDate={s}&endDate={e}&api_key={key}", 'DONKI/GST') or []
        return {'sep': sep, 'flares': flr, 'cme': cme, 'geoStorms': gst}
    except Exception:
        return {'sep': [], 'flares': [], 'cme': [], 'geoStorms': []}

def fetch_noaa():
    try:
        xray = safe_api('https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json', 'NOAA/xray') or []
        protons = safe_api(CONFIG['RADIATION_APIS']['INTEGRAL'], 'NOAA/protons') or []
        kp = safe_api('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json', 'NOAA/kp') or []
        mag = safe_api('https://services.swpc.noaa.gov/json/goes/primary/magnetometers-1-day.json', 'NOAA/mag') or []
        integral = safe_api(CONFIG['RADIATION_APIS']['INTEGRAL'], 'rad/integral') or []
        differential = safe_api(CONFIG['RADIATION_APIS']['DIFFERENTIAL'], 'rad/diff') or []
        electrons = safe_api(CONFIG['RADIATION_APIS']['ELECTRONS'], 'rad/electrons') or []
        xpri = safe_api(CONFIG['RADIATION_APIS']['XRAY_PRI'], 'rad/xpri') or []
        xsec = safe_api(CONFIG['RADIATION_APIS']['XRAY_SEC'], 'rad/xsec') or []
        radData = {
            'protons': {'integral': integral, 'differential': differential},
            'electrons': electrons,
            'xray': {'primary': xpri, 'secondary': xsec}
        }
        return {'xray': xray, 'protons': protons, 'kp': kp, 'magnetometer': mag, 'radData': radData}
    except Exception:
        return {'xray': [], 'protons': [], 'kp': [], 'magnetometer': [], 'radData': {}}

def fetch_historical():

    return {
        'diviner':  {'equator':{'day':390,'night':100}, 'midLat':{'day':380,'night':95}, 'polar':{'day':220,'night':40}},
        'ldex':     {'southPole':{'density':1.2e-15,'var':0.3e-15}, 'equator':{'density':1.5e-15,'var':0.4e-15}},
        'pse':      {'deep':{'avgPerDay':28,'mag':2.5}, 'shallow':{'avgPerDay':3,'mag':4.2}, 'thermal':{'avgPerDay':15,'mag':1.8}},
        'mem':      {'flux':{'min':1.1e-15,'avg':1.6e-15,'max':3.2e-15}},
        'apollo':   {'measurements':[{'loc':'Hadley Rille','heatFlow':21},{'loc':'Taurus-Littrow','heatFlow':16}]}
    }

def calc_meteor_flux(date=None, loc=None):
    avg = historical_data.get('mem', {}).get('flux', {}).get('avg', 1.6)

    try:
        t = time.gmtime() if date is None else time.gmtime(date.timestamp())
        doy = int(time.strftime('%j', t))

        frac = 1.0 + 0.12 * np.sin(2*np.pi*(doy/365.0))
        return float(avg * frac)
    except Exception:
        return float(avg)

def calc_dust_activity(date=None, loc=None):
    base = historical_data.get('ldex', {}).get('equator', {}).get('density', 1.5e-15)

    proxy = 1.5

    mf = calc_meteor_flux(date, loc)
    scale = 1.0 + (mf - 1.6) * 0.12
    return float(max(0.5, min(5.0, proxy * scale)))

def physics_estimate(inputs, lat=None, lon=None, local_time=None, day_of_year=None, extra=None):
    solar, rad, temp, quakes, flux, dust = [float(v) for v in inputs]
    extra = extra or {}
    kp_proxy = float(extra.get('kp_index', estimate_kp_proxy(solar, rad)))
    sw_speed = float(extra.get('solar_wind_speed', clamp(400.0 + solar * 8.0, 250.0, 900.0, 400.0)))
    sw_dens = float(extra.get('solar_wind_density', clamp(5.0 + solar * 0.1, 0.5, 50.0, 5.0)))
    imf_bz = float(extra.get('imf_bz', clamp(-2.0 - rad * 2.0, -30.0, 30.0, -2.0)))

    if lat is not None and lon is not None and (
        extra.get('terrain') is None or extra.get('thermal_inertia') is None
    ):
        site_reg, site_ti, site_terrain, site_alb, site_emis = _nearest_site_material(lat, lon)
        extra.setdefault('regolith_depth', site_reg)
        extra.setdefault('thermal_inertia', site_ti)
        extra.setdefault('terrain', site_terrain)
        extra.setdefault('albedo', site_alb)
        extra.setdefault('emissivity', site_emis)
    terrain = extra.get('terrain')

    if day_of_year is None:
        day_of_year = int(time.strftime('%j', time.gmtime()))

    phys_temp = physics_temperature(
        lat or 0.0, lon or 0.0, local_time or 12.0,
        day_of_year=int(day_of_year), terrain=terrain,
        albedo=extra.get('albedo'), emissivity=extra.get('emissivity'),
        thermal_inertia=extra.get('thermal_inertia'),
    )

    try:
        from data_ingestion import (
            load_diviner_site_climatology, diviner_temp_C,
            load_diviner_prp_polar_temps, diviner_prp_polar_temp_C,
        )
        from lunar_sites import nearest_site
        _clim = load_diviner_site_climatology()
        if _clim and lat is not None and lon is not None:
            _site = nearest_site(float(lat), float(lon))
            _div = diviner_temp_C(_clim, _site.name, local_time if local_time is not None else 12.0)
            _diviner_used = False
            if _div is not None:
                phys_temp = 0.75 * float(_div) + 0.25 * float(phys_temp)
                _diviner_used = True

            if abs(float(lat)) >= 70.0:
                _prp = load_diviner_prp_polar_temps()
                _prp_t = diviner_prp_polar_temp_C(_prp, _site.name)
                if _prp_t is not None:
                    phys_temp = 0.55 * float(_prp_t) + 0.45 * float(phys_temp)
                    _diviner_used = True
            if _diviner_used:
                extra['diviner_blend'] = True
    except Exception:
        pass

    if extra.get('proton_flux') is not None:
        try:
            proton_proxy = max(0.05, float(extra['proton_flux']))
        except Exception:
            proton_proxy = max(1.0, rad * 40.0 + max(0.0, solar - 8.0) * 0.5)
    else:
        proton_proxy = max(1.0, rad * 40.0 + max(0.0, solar - 8.0) * 0.5)
    phys_rad = physics_radiation(
        solar_activity=solar, kp=kp_proxy, proton_flux=proton_proxy,
        lat=lat, imf_bz=imf_bz, solar_wind_speed=sw_speed,
    )
    phys_flux = physics_micrometeorite_flux(
        day_of_year=int(day_of_year), shower_factor=1.0, lat=lat,
    )
    ldex_factor = 1.0
    if extra.get('ldex_factor') is not None:
        try:
            ldex_factor = float(extra['ldex_factor'])
        except Exception:
            ldex_factor = 1.0
    try:
        phys_dust = physics_dust(
            phys_flux, lat=lat, local_time=local_time,
            ldex_factor=ldex_factor,
            regolith_depth=extra.get('regolith_depth'),
        )
    except TypeError:
        try:
            phys_dust = physics_dust(phys_flux, lat=lat, local_time=local_time, ldex_factor=ldex_factor)
        except TypeError:
            phys_dust = physics_dust(phys_flux)
    try:
        phys_quakes = physics_moonquake_rate(
            lat=lat, local_time=local_time,
            regolith_depth=extra.get('regolith_depth'),
        )
    except TypeError:
        phys_quakes = physics_moonquake_rate()

    if quakes > 5.0:
        phys_quakes = 0.35 * phys_quakes + 0.65 * quakes

    sw = analyze_space_weather(real_time_data)
    if sw.get('solarStorms', {}).get('level') == 'red':
        phys_rad = max(phys_rad, phys_rad * 1.12)
        kp_proxy = max(kp_proxy, 7.0)
    if sw.get('radiation', {}).get('value', 0) > phys_rad:
        phys_rad = sw['radiation']['value']

    phys_solar = physics_solar_activity(
        solar_activity=solar, kp=kp_proxy, imf_bz=imf_bz,
        solar_wind_speed=sw_speed, solar_wind_density=sw_dens,
        f107=extra.get('f107'),
    )

    out = {
        'solar': float(clamp(phys_solar, 0.0, 80.0, solar)),
        'radiation': float(clamp(phys_rad, 0.01, 10.0, phys_rad)),
        'temperature': float(clamp(phys_temp, -230.0, 130.0, phys_temp)),
        'moonquakes': float(clamp(phys_quakes, 0.0, 200.0, phys_quakes)),
        'micrometeorites': float(clamp(phys_flux, 0.8, 8.0, phys_flux)),
        'dust': float(clamp(phys_dust, 0.5, 6.0, phys_dust)),
        'regime': detect_storm_regime(phys_solar, kp_proxy, phys_rad, imf_bz),
    }
    if extra.get('diviner_blend'):
        out['diviner_blend'] = True
    try:
        from lunar_physics import load_mem3_flux_summary
        if load_mem3_flux_summary():
            out['mem3_blend'] = True
    except Exception:
        pass
    return out

def _nearest_site_material(lat, lon):
    try:
        from lunar_sites import nearest_site
        best = nearest_site(lat, lon)
        return (
            float(best.regolith_depth),
            float(best.thermal_inertia),
            str(best.terrain),
            float(best.albedo),
            float(best.emissivity),
        )
    except Exception:
        return 4.5, 50.0, 'mare', 0.07, 0.95

def build_expanded_features(inputs, lat=None, lon=None, local_time=None, extra=None, timestamp=None):
    inputs = list(inputs)
    if len(inputs) >= NUM_EXPANDED_FEATURES:
        return np.asarray(inputs[:NUM_EXPANDED_FEATURES], dtype=np.float32)

    core = [float(v) for v in inputs[:NUM_CORE_FEATURES]]
    while len(core) < NUM_CORE_FEATURES:
        core.append(0.0)
    solar_activity, radiation = core[0], core[1]

    extra = extra or {}
    t = time.gmtime(timestamp) if timestamp is not None else time.gmtime()

    lat_v = float(lat) if lat is not None else float(extra.get('lat', 0.0))
    lon_v = float(lon) if lon is not None else float(extra.get('lon', 0.0))
    local_solar_time = float(local_time) if local_time is not None else float(extra.get('local_solar_time', t.tm_hour))

    hour_of_day = float(extra.get('hour_of_day', t.tm_hour))
    day_of_month = float(extra.get('day_of_month', t.tm_mday))
    month_of_year = float(extra.get('month_of_year', t.tm_mon))

    kp_default = estimate_kp_proxy(solar_activity, radiation)

    try:
        from gap_fill import cross_fill_omni_drivers
        import pandas as _pd
        _drv = _pd.DataFrame([{
            'solar_wind_speed': extra.get('solar_wind_speed'),
            'solar_wind_density': extra.get('solar_wind_density'),
            'imf_bz': extra.get('imf_bz'),
            'kp_index': extra.get('kp_index'),
            'f107': extra.get('f107'),
            'dst': extra.get('dst'),
            'ap': extra.get('ap'),
            'ssn': extra.get('ssn'),
        }])
        _drv = cross_fill_omni_drivers(_drv)
        for _k in ('solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'f107', 'dst', 'ap'):
            if _k in _drv.columns and _pd.notna(_drv.iloc[0][_k]):
                extra.setdefault(_k, float(_drv.iloc[0][_k]))
    except Exception:
        pass
    solar_wind_speed = float(extra.get('solar_wind_speed', clamp(400.0 + solar_activity * 8.0, 250.0, 900.0, 400.0)))
    solar_wind_density = float(extra.get('solar_wind_density', clamp(5.0 + solar_activity * 0.1, 0.5, 50.0, 5.0)))
    imf_bz = float(extra.get('imf_bz', clamp(-2.0 - radiation * 2.0, -30.0, 30.0, -2.0)))
    kp_index = float(extra.get('kp_index', kp_default))

    site_reg, site_ti, site_terrain, site_alb, site_emis = _nearest_site_material(lat_v, lon_v)
    regolith_depth = float(extra.get('regolith_depth', site_reg))
    thermal_inertia = float(extra.get('thermal_inertia', site_ti))

    extra.setdefault('terrain', site_terrain)
    extra.setdefault('albedo', site_alb)
    extra.setdefault('emissivity', site_emis)
    extra.setdefault('regolith_depth', regolith_depth)
    extra.setdefault('thermal_inertia', thermal_inertia)

    vector = core + [
        lat_v, lon_v, local_solar_time,
        hour_of_day, day_of_month, month_of_year,
        solar_wind_speed, solar_wind_density, imf_bz, kp_index,
        regolith_depth, thermal_inertia
    ]
    return np.asarray(vector, dtype=np.float32)

def record_feature_history(vector, lat=None, lon=None, timestamp=None):
    key = _site_key(lat, lon)
    day = time.strftime('%Y-%m-%d', time.gmtime(timestamp) if timestamp is not None else time.gmtime())
    vec = np.asarray(vector, dtype=np.float32).copy()
    with _FEATURE_HISTORY_LOCK:
        entry = _FEATURE_HISTORY_BY_SITE.get(key)
        if entry is None:
            if len(_FEATURE_HISTORY_BY_SITE) >= _MAX_TRACKED_SITES:
                _FEATURE_HISTORY_BY_SITE.popitem(last=False)
            entry = {'date': day, 'deque': collections.deque(maxlen=SEQUENCE_LENGTH)}
            _FEATURE_HISTORY_BY_SITE[key] = entry
        else:
            _FEATURE_HISTORY_BY_SITE.move_to_end(key)
        if entry['date'] == day and len(entry['deque']) > 0:
            entry['deque'][-1] = vec
        else:
            entry['deque'].append(vec)
            entry['date'] = day

def _diurnal_pad_history(seed_vector, n_pad, lat=None, lon=None):
    seed = np.asarray(seed_vector, dtype=np.float32).copy()
    dim = seed.shape[0]
    out = []

    idx_lst, idx_hod, idx_dom, idx_moy = 8, 9, 10, 11
    idx_temp = 2
    for i in range(n_pad):
        v = seed.copy()

        hour = float((12.0 - (n_pad - i)) % 24.0)
        if dim > idx_lst:
            v[idx_lst] = hour / 24.0 if abs(seed[idx_lst]) <= 1.5 else hour
        if dim > idx_hod:
            v[idx_hod] = hour
        if dim > idx_temp:

            v[idx_temp] = seed[idx_temp] + 0.15 * np.sin(2.0 * np.pi * hour / 24.0)
        if dim > idx_dom:
            v[idx_dom] = seed[idx_dom]
        if dim > idx_moy:
            v[idx_moy] = seed[idx_moy]
        out.append(v)
    return out

def build_sequence_window(current_vector, sequence_length=SEQUENCE_LENGTH, lat=None, lon=None):
    current_vector = np.asarray(current_vector, dtype=np.float32)
    key = _site_key(lat, lon)
    with _FEATURE_HISTORY_LOCK:
        entry = _FEATURE_HISTORY_BY_SITE.get(key)
        history = list(entry['deque']) if entry is not None else []
    if not history:
        history = [current_vector]
    if len(history) < sequence_length:
        need = sequence_length - len(history)
        pad = _diurnal_pad_history(history[0], need, lat=lat, lon=lon)
        history = pad + history
    else:
        history = history[-sequence_length:]
    return np.stack(history, axis=0)

def warm_start_feature_history(model_dir=MODEL_DIR, csv_glob='data/ingested_extended/extended_training_*.csv', max_sites=32):
    global _SCALER
    import glob as _glob
    candidates = sorted(_glob.glob(csv_glob), key=os.path.getmtime)
    if not candidates:
        return 0
    csv_path = candidates[-1]
    try:
        import pandas as pd
    except ImportError:
        return 0
    if _SCALER is None:
        _SCALER = load_scaler(model_dir)
    if _SCALER is None:
        return 0
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return 0
    if 'site' not in df.columns:
        return 0
    from data_ingestion import get_training_columns
    cols = [c for c in get_training_columns() if c in df.columns]
    if len(cols) < NUM_CORE_FEATURES:
        return 0
    seeded = 0
    for site_name, g in df.groupby('site'):
        if seeded >= max_sites:
            break
        g = g.sort_values('date') if 'date' in g.columns else g
        tail = g.tail(SEQUENCE_LENGTH)
        if len(tail) < 8:
            continue
        X = tail[cols].to_numpy(dtype=np.float32)

        mean = _SCALER['mean']
        if X.shape[1] < mean.shape[0]:
            pad = np.zeros((X.shape[0], mean.shape[0] - X.shape[1]), dtype=np.float32)
            X = np.concatenate([X, pad], axis=1)
        elif X.shape[1] > mean.shape[0]:
            X = X[:, :mean.shape[0]]
        Xs = apply_scaler(X, _SCALER)
        lat = float(tail['lat'].iloc[-1]) if 'lat' in tail.columns else 0.0
        lon = float(tail['lon'].iloc[-1]) if 'lon' in tail.columns else 0.0
        key = _site_key(lat, lon)
        with _FEATURE_HISTORY_LOCK:
            if len(_FEATURE_HISTORY_BY_SITE) >= _MAX_TRACKED_SITES:
                _FEATURE_HISTORY_BY_SITE.popitem(last=False)
            dq = collections.deque(maxlen=SEQUENCE_LENGTH)
            for row in Xs:
                dq.append(np.asarray(row, dtype=np.float32))
            day = str(tail['date'].iloc[-1])[:10] if 'date' in tail.columns else time.strftime('%Y-%m-%d', time.gmtime())
            _FEATURE_HISTORY_BY_SITE[key] = {'date': day, 'deque': dq}
        seeded += 1
    return seeded

def make_sliding_windows(X, Y=None, sequence_length=SEQUENCE_LENGTH, stride=1):
    X = np.asarray(X, dtype=np.float32)
    n = X.shape[0]
    if n < sequence_length:
        raise ValueError(f'Need at least {sequence_length} rows to build a {sequence_length}-step sliding window (got {n}).')
    starts = list(range(0, n - sequence_length + 1, max(1, int(stride))))
    n_features = X.shape[1]
    X_seq = np.zeros((len(starts), sequence_length, n_features), dtype=np.float32)
    for out_i, i in enumerate(starts):
        X_seq[out_i] = X[i:i + sequence_length]
    if Y is not None:
        Y = np.asarray(Y, dtype=np.float32)
        Y_seq = np.stack([Y[i + sequence_length - 1] for i in starts], axis=0)
        return X_seq, Y_seq
    return X_seq

def make_sliding_windows_grouped(X, Y, groups, sequence_length=SEQUENCE_LENGTH, stride=1):
    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32) if Y is not None else None
    groups = np.asarray(groups)

    X_windows, Y_windows = [], []
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        Xg = X[idx]
        if len(Xg) < sequence_length:
            continue
        if Y is not None:
            Xw, Yw = make_sliding_windows(Xg, Y[idx], sequence_length=sequence_length, stride=stride)
            Y_windows.append(Yw)
        else:
            Xw = make_sliding_windows(Xg, None, sequence_length=sequence_length, stride=stride)
        X_windows.append(Xw)

    if not X_windows:
        raise ValueError(f'No group in `groups` has at least {sequence_length} rows to build a window.')
    X_out = np.concatenate(X_windows, axis=0)
    if Y is not None:
        return X_out, np.concatenate(Y_windows, axis=0)
    return X_out

def fit_calibration(raw_preds, targets, method='platt'):
    raw = np.asarray(raw_preds, dtype=np.float64).reshape(-1, np.asarray(raw_preds).shape[-1])
    tgt = np.asarray(targets, dtype=np.float64).reshape(-1, np.asarray(targets).shape[-1])
    n_outputs = raw.shape[1]

    if method == 'isotonic':
        try:
            from sklearn.isotonic import IsotonicRegression
            calibrators = []
            for i in range(n_outputs):
                ir = IsotonicRegression(out_of_bounds='clip')
                ir.fit(raw[:, i], tgt[:, i])
                calibrators.append(ir)
            return {'method': 'isotonic', 'calibrators': calibrators, 'n_outputs': n_outputs}
        except Exception:
            method = 'platt'

    A = np.ones(n_outputs)
    B = np.zeros(n_outputs)
    for i in range(n_outputs):
        x = raw[:, i]
        y = tgt[:, i]
        if np.std(x) < 1e-8 or np.std(y) < 1e-8:
            A[i], B[i] = 1.0, 0.0
            continue
        design = np.vstack([x, np.ones_like(x)]).T
        sol, *_ = np.linalg.lstsq(design, y, rcond=None)
        a_i, b_i = float(sol[0]), float(sol[1])

        if not np.isfinite(a_i) or a_i < 0.05 or a_i > 2.5:
            A[i], B[i] = 1.0, 0.0
        else:
            A[i], B[i] = a_i, b_i
    return {'method': 'platt', 'A': A, 'B': B, 'n_outputs': n_outputs}

def save_calibration(calib, model_dir=MODEL_DIR):
    os.makedirs(model_dir, exist_ok=True)
    if calib is None:
        return
    if calib.get('method') == 'isotonic':
        import pickle
        with open(os.path.join(model_dir, 'calibration.pkl'), 'wb') as f:
            pickle.dump(calib, f)

        try:
            os.remove(os.path.join(model_dir, 'calibration.npz'))
        except Exception:
            pass
    else:
        np.savez(os.path.join(model_dir, 'calibration.npz'), A=calib['A'], B=calib['B'])
        try:
            os.remove(os.path.join(model_dir, 'calibration.pkl'))
        except Exception:
            pass

def load_calibration(model_dir=MODEL_DIR):
    pkl_path = os.path.join(model_dir, 'calibration.pkl')
    npz_path = os.path.join(model_dir, 'calibration.npz')
    if os.path.exists(pkl_path):
        try:
            import pickle
            with open(pkl_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    if os.path.exists(npz_path):
        try:
            data = np.load(npz_path, allow_pickle=True)
            return {'method': 'platt', 'A': data['A'], 'B': data['B']}
        except Exception:
            pass
    return None

def apply_calibration(preds, calib):
    if calib is None:
        return preds
    preds_arr = np.asarray(preds, dtype=np.float64)
    if calib.get('method') == 'isotonic':
        out = preds_arr.copy()
        for i, ir in enumerate(calib.get('calibrators', [])):
            if i < out.shape[-1]:
                flat = out[..., i].reshape(-1)
                out[..., i] = ir.predict(flat).reshape(out[..., i].shape)
        return out
    A = calib.get('A')
    B = calib.get('B')
    if A is None or B is None:
        return preds_arr
    return preds_arr * A + B

def _resolve_model_feature_dim(model=None, ensemble=None, scaler=None):
    if scaler is not None:
        try:
            return int(scaler['mean'].shape[0])
        except Exception:
            pass
    candidate = None
    if ensemble:
        candidate = ensemble[0] if isinstance(ensemble, (list, tuple)) else ensemble
    elif model is not None:
        candidate = model
    if candidate is not None:
        try:
            shape = candidate.input_shape
            if isinstance(shape, list):
                shape = shape[0]
            return int(shape[-1])
        except Exception:
            pass
    return None

def _feature_vector_for_dim(target_dim, inputs, lat=None, lon=None, local_time=None, extra=None):
    core_vals = [float(v) for v in list(inputs)[:NUM_CORE_FEATURES]]
    while len(core_vals) < NUM_CORE_FEATURES:
        core_vals.append(0.0)
    if target_dim == NUM_CORE_FEATURES:
        return np.asarray(core_vals, dtype=np.float32)
    expanded = build_expanded_features(inputs, lat=lat, lon=lon, local_time=local_time, extra=extra)
    if target_dim is not None and target_dim != len(expanded):
        if target_dim < len(expanded):
            return expanded[:target_dim]
        return np.pad(expanded, (0, target_dim - len(expanded)))
    return expanded

MC_DROPOUT_PASSES = int(os.environ.get('MC_DROPOUT_PASSES', '8'))

def mc_dropout_predict(model, X, n_passes=MC_DROPOUT_PASSES):
    try:
        X_t = tf.convert_to_tensor(np.asarray(X, dtype=np.float32))
        passes = np.stack([np.asarray(model(X_t, training=True)) for _ in range(max(2, int(n_passes)))], axis=0)
        return passes.mean(axis=0), passes.std(axis=0)
    except Exception:
        try:
            return np.asarray(model.predict(X, verbose=0)), None
        except Exception:
            raise

def model_predict(inputs, model=None, use_ensemble=False, lat=None, lon=None, local_time=None, extra=None):
    global _MODEL, _ENSEMBLE, _SCALER, _CALIBRATION
    if model is None:
        model = _MODEL

    if model is None and (not use_ensemble or not _ENSEMBLE):
        global _SURROGATE_COEFFS, _SURROGATE_INTERCEPT
        with _SURROGATE_LOCK:
            if _SURROGATE_COEFFS is not None:
                core = np.asarray(list(inputs)[:NUM_CORE_FEATURES], dtype=np.float32).reshape(1, -1)
                Y = core.dot(_SURROGATE_COEFFS.T) + _SURROGATE_INTERCEPT
                return {'mean': Y.flatten().tolist(), 'std': None, 'surrogate': True}
        return None

    target_dim = _resolve_model_feature_dim(model=model, ensemble=_ENSEMBLE if use_ensemble else None, scaler=_SCALER)
    feature_vector = _feature_vector_for_dim(target_dim, inputs, lat=lat, lon=lon, local_time=local_time, extra=extra)
    X = feature_vector.reshape(1, -1)
    if _SCALER is not None and _SCALER['mean'].shape[0] == X.shape[1]:
        X_scaled = apply_scaler(X, _SCALER)
    else:
        X_scaled = X
    record_feature_history(X_scaled.flatten(), lat=lat, lon=lon)

    if use_ensemble and _ENSEMBLE:
        mean, std = ensemble_predict(_ENSEMBLE, X_scaled)
        if mean is None:
            return None
        mean = apply_calibration(mean, _CALIBRATION)
        return {
            'mean': np.asarray(mean).flatten().tolist(),
            'std': std.flatten().tolist() if std is not None else None,
            'uncertainty_source': 'ensemble',
        }

    try:
        input_shape = model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]
        if len(input_shape) == 3:
            seq_len = input_shape[1] or SEQUENCE_LENGTH
            window = build_sequence_window(X_scaled.flatten(), sequence_length=seq_len, lat=lat, lon=lon)
            model_input = window.reshape(1, *window.shape)
        else:
            model_input = X_scaled

        mean, std = mc_dropout_predict(model, model_input)
        mean = apply_calibration(mean, _CALIBRATION)
        return {
            'mean': np.asarray(mean).flatten().tolist(),
            'std': std.flatten().tolist() if std is not None else None,
            'uncertainty_source': 'mc_dropout' if std is not None else None,
        }
    except Exception:
        return None

def init_surrogate(n_samples=256, random_seed=42):
    global _SURROGATE_COEFFS, _SURROGATE_INTERCEPT
    rs = np.random.RandomState(random_seed)
    X = []
    Y = []
    for i in range(n_samples):

        solar = rs.uniform(0.0, 25.0)
        rad = rs.uniform(0.03, 0.3)
        temp = rs.uniform(-180.0, 140.0)
        quakes = rs.uniform(0.0, 30.0)
        flux = rs.uniform(0.8, 3.5)
        dust = rs.uniform(0.5, 3.5)
        inp = [solar, rad, temp, quakes, flux, dust]
        phys = physics_estimate(inp)

        targ = [
            phys['solar'] * (1.0 + rs.normal(0, 0.03)),
            phys['radiation'] * (1.0 + rs.normal(0, 0.05)),
            phys['temperature'] + rs.normal(0, 2.5),
            phys['moonquakes'] * (1.0 + rs.normal(0, 0.07)),
            phys['micrometeorites'] * (1.0 + rs.normal(0, 0.05)),
            phys['dust'] * (1.0 + rs.normal(0, 0.05))
        ]
        X.append(inp)
        Y.append(targ)
    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)

    A = np.concatenate([X, np.ones((X.shape[0], 1), dtype=np.float32)], axis=1)
    try:
        sol, *_ = np.linalg.lstsq(A, Y, rcond=None)
        W = sol[:-1, :].T
        b = sol[-1, :]
        with _SURROGATE_LOCK:
            _SURROGATE_COEFFS = W
            _SURROGATE_INTERCEPT = b
        return True
    except Exception:
        return False

def surrogate_predict(inputs):
    global _SURROGATE_COEFFS, _SURROGATE_INTERCEPT
    with _SURROGATE_LOCK:
        if _SURROGATE_COEFFS is None:
            return None
        X = np.asarray(inputs, dtype=np.float32).reshape(1, -1)
        Y = X.dot(_SURROGATE_COEFFS.T) + _SURROGATE_INTERCEPT
        return {'mean': Y.flatten().tolist(), 'std': None, 'surrogate': True}

def get_channel_blend_weights(scalar_fallback=None):
    global _CHANNEL_ML_BLEND_WEIGHTS
    if _CHANNEL_ML_BLEND_WEIGHTS is not None and len(_CHANNEL_ML_BLEND_WEIGHTS) == NUM_CORE_FEATURES:
        return list(_CHANNEL_ML_BLEND_WEIGHTS)
    w = float(DEFAULT_ML_BLEND_WEIGHT if scalar_fallback is None else scalar_fallback)
    return [w] * NUM_CORE_FEATURES

def load_blend_weights(model_dir=MODEL_DIR):
    global _CHANNEL_ML_BLEND_WEIGHTS, DEFAULT_ML_BLEND_WEIGHT
    npy = os.path.join(model_dir, 'blend_weights.npy')
    meta_path = os.path.join(model_dir, 'meta.json')
    try:
        if os.path.exists(npy):
            arr = np.load(npy).astype(np.float64).flatten()
            if arr.shape[0] == NUM_CORE_FEATURES:
                _CHANNEL_ML_BLEND_WEIGHTS = [float(clamp(x, 0.0, 1.0, DEFAULT_ML_BLEND_WEIGHT)) for x in arr]
                return _CHANNEL_ML_BLEND_WEIGHTS
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            bw = meta.get('blend_weights') or meta.get('channel_ml_blend_weights')
            if isinstance(bw, dict):
                _CHANNEL_ML_BLEND_WEIGHTS = [
                    float(clamp(bw.get(k, DEFAULT_ML_BLEND_WEIGHT), 0.0, 1.0, DEFAULT_ML_BLEND_WEIGHT))
                    for k in CORE_FEATURE_NAMES
                ]
                return _CHANNEL_ML_BLEND_WEIGHTS
            if isinstance(bw, (list, tuple)) and len(bw) == NUM_CORE_FEATURES:
                _CHANNEL_ML_BLEND_WEIGHTS = [float(clamp(x, 0.0, 1.0, DEFAULT_ML_BLEND_WEIGHT)) for x in bw]
                return _CHANNEL_ML_BLEND_WEIGHTS
            best = meta.get('best_physics_weight')
            if best is not None:

                DEFAULT_ML_BLEND_WEIGHT = float(clamp(best, 0.0, 1.0, DEFAULT_ML_BLEND_WEIGHT))
    except Exception:
        pass
    return None

def adaptive_channel_blend_weights(base_weights, physics_dict, ml_std=None, inputs=None, local_time=None):
    w = [float(x) for x in base_weights]
    regime = (physics_dict or {}).get('regime') or {}
    level = regime.get('level', 'quiet')
    if level == 'storm':

        w[0] = min(1.0, w[0] + 0.12)
        w[1] = min(1.0, w[1] + 0.08)
        w[2] = max(0.0, w[2] - 0.05)
        w[4] = max(0.0, w[4] - 0.04)
        w[5] = max(0.0, w[5] - 0.04)
    elif level == 'unsettled':
        w[0] = min(1.0, w[0] + 0.05)
        w[1] = min(1.0, w[1] + 0.04)

    if local_time is not None:
        try:
            hour = float(local_time) % 24.0
            dist_sr = min(abs(hour - 6.0), 24.0 - abs(hour - 6.0))
            dist_ss = min(abs(hour - 18.0), 24.0 - abs(hour - 18.0))
            if min(dist_sr, dist_ss) < 2.5:
                w[5] = max(0.0, w[5] * 0.75)
                w[3] = max(0.0, w[3] * 0.90)
        except Exception:
            pass

    if isinstance(physics_dict, dict) and physics_dict.get('dust') is not None:
        try:
            if float(physics_dict['dust']) > 2.0:
                w[5] = max(0.0, min(w[5], w[5] * 0.85))
        except Exception:
            pass

    if isinstance(physics_dict, dict) and physics_dict.get('diviner_blend'):
        w[2] = min(w[2], 0.70)

    if isinstance(physics_dict, dict) and physics_dict.get('mem3_blend'):
        w[4] = min(w[4], 0.15)

    if ml_std is not None:
        try:
            std = np.asarray(ml_std, dtype=np.float64).flatten()
            spans = np.array([hi - lo for lo, hi in PHYSICAL_OUTPUT_BOUNDS], dtype=np.float64)
            for i in range(min(len(w), len(std))):
                rel = float(std[i] / max(spans[i], 1e-6))

                shrink = float(clamp(1.0 - 1.6 * rel, 0.35, 1.0, 1.0))
                w[i] = float(clamp(w[i] * shrink, 0.0, 1.0, w[i]))
        except Exception:
            pass

    if inputs is not None and len(inputs) > 1 and float(inputs[1]) > 0.25:
        w[1] = min(w[1], 0.35)
    return w

def refine_prediction(inputs, lat=None, lon=None, local_time=None, physics_weight=DEFAULT_ML_BLEND_WEIGHT, use_ensemble=False, extra=None, day_of_year=None):
    extra = dict(extra or {})
    if day_of_year is None:
        day_of_year = extra.get('day_of_year')
    if day_of_year is None and extra.get('date') is not None:
        try:
            from datetime import datetime as _dt
            _d = extra['date']
            if hasattr(_d, 'timetuple'):
                day_of_year = int(_d.timetuple().tm_yday)
            else:
                day_of_year = int(_dt.fromisoformat(str(_d)[:10]).timetuple().tm_yday)
        except Exception:
            day_of_year = None
    if day_of_year is not None:
        extra['day_of_year'] = int(day_of_year)
    base = physics_estimate(
        inputs, lat=lat, lon=lon, local_time=local_time,
        day_of_year=None if day_of_year is None else int(day_of_year),
        extra=extra,
    )
    model_out = model_predict(inputs, use_ensemble=use_ensemble, lat=lat, lon=lon, local_time=local_time, extra=extra)
    if model_out is None:
        plaus = plausibility_score(base, inputs, lat=lat, lon=lon, local_time=local_time)
        return {'hybrid': {k: base[k] for k in ('solar', 'radiation', 'temperature', 'moonquakes', 'micrometeorites', 'dust')},
                'physics': base, 'ml': None, 'plausibility': plaus,
                'confidence': {'overall_pct': round(100.0 * plaus, 1), 'per_channel_pct': None,
                               'basis': 'physics_plausibility_only', 'model_uncertainty_available': False},
                'regime': base.get('regime')}

    ml_mean = model_out['mean']
    ml_pred = {
        'solar': ml_mean[0],
        'radiation': ml_mean[1],
        'temperature': ml_mean[2],
        'moonquakes': ml_mean[3],
        'micrometeorites': ml_mean[4],
        'dust': ml_mean[5]
    }

    base_weights = get_channel_blend_weights(scalar_fallback=physics_weight)
    weights = adaptive_channel_blend_weights(
        base_weights, base, ml_std=model_out.get('std'), inputs=inputs, local_time=local_time,
    )
    keys = ['solar', 'radiation', 'temperature', 'moonquakes', 'micrometeorites', 'dust']

    bounds = list(PHYSICAL_OUTPUT_BOUNDS)
    hybrid = {}
    for i, k in enumerate(keys):
        w = float(weights[i])
        hybrid[k] = float(clamp(
            w * ml_pred[k] + (1.0 - w) * base[k],
            bounds[i][0], bounds[i][1], base[k],
        ))
    confidence = combined_confidence_pct(model_out.get('std'), hybrid, inputs, lat=lat, lon=lon, local_time=local_time)
    return {
        'hybrid': hybrid,
        'physics': base,
        'ml': {'prediction': ml_pred, 'uncertainty': model_out.get('std'), 'uncertainty_source': model_out.get('uncertainty_source')},
        'plausibility': plausibility_score(hybrid, inputs, lat=lat, lon=lon, local_time=local_time),
        'confidence': confidence,
        'blend_weights': {keys[i]: weights[i] for i in range(6)},
        'blend_weights_base': {keys[i]: base_weights[i] for i in range(6)},
        'regime': base.get('regime'),
    }

def analyze_space_weather(data):
    out = {
        'radiation': {'level': 'green', 'value': 0.057, 'confidence': 85, 'variance': 0.008},
        'solarStorms': {'level': 'green', 'value': 0, 'confidence': 80},
        'solarActivity': {'value': 5, 'illumination': 0, 'confidence': 75}
    }
    try:

        out['radiation']['value'] = out['radiation']['value'] + calc_gcr_radiation()

        if data.get('nasa') and data['nasa'].get('sep') and len(data['nasa']['sep'])>0:
            week = [e for e in data['nasa']['sep'] if (time.time()*1000 - int(parse_time_ms(e.get('eventTime') or 0))) < 7*864e5]
            if len(week)>0:
                out['radiation']['value'] *= 1.2
                out['solarStorms']['level'] = 'yellow'

        if data.get('nasa') and data['nasa'].get('flares') and len(data['nasa']['flares'])>0:
            recent = data['nasa']['flares']
            xF = [f for f in recent if f.get('classType','').startswith('X')]
            mF = [f for f in recent if f.get('classType','').startswith('M')]
            score = len(xF)*10 + len(mF)*5
            out['solarActivity']['value'] = min(30, 5 + score * 0.8)
            if len(xF)>0: out['solarStorms']['level'] = 'red'
            elif len(mF)>0: out['solarStorms']['level'] = 'yellow'

        if data.get('nasa') and data['nasa'].get('cme') and len(data['nasa']['cme'])>0:
            out['solarStorms']['level'] = 'yellow' if out['solarStorms']['level'] != 'red' else 'red'
    except Exception:
        pass
    return out

def parse_time_ms(ts):
    try:
        if isinstance(ts, (int,float)):
            return int(ts)

        return int(time.mktime(time.strptime(ts.split('.')[0], "%Y-%m-%dT%H:%M:%S")) * 1000)
    except Exception:
        return 0

def fetch_all_data():
    global real_time_data, historical_data, radiation_cache
    try:
        donki = fetch_donki()
        noaa = fetch_noaa()
        hist = fetch_historical()
        real_time_data = {'nasa': donki, 'noaa': noaa, 'timestamp': int(time.time()*1000)}
        historical_data = hist
        radiation_cache = {'hourly': [], 'daily': [], 'timestamp': int(time.time()*1000), 'raw': noaa.get('radData', {})}
    except Exception:
        pass

def background_updater(interval_sec=900):
    while True:
        try:
            fetch_all_data()
        except Exception:
            pass
        time.sleep(interval_sec)

def predict_space_weather(inputs, model=None, lat=None, lon=None, local_time=None, extra=None):
    if len(inputs) != NUM_CORE_FEATURES:
        raise ValueError(f'inputs must be a {NUM_CORE_FEATURES}-element list or array')

    fast = physics_estimate(inputs, lat=lat, lon=lon, local_time=local_time)
    if model is None:
        model = _MODEL

    if model is None and not _ENSEMBLE:
        return fast

    refined = refine_prediction(inputs, lat=lat, lon=lon, local_time=local_time, physics_weight=DEFAULT_ML_BLEND_WEIGHT, use_ensemble=bool(_ENSEMBLE), extra=extra)
    if refined and 'hybrid' in refined:
        return refined['hybrid']
    return fast

def load_scaler(model_dir=MODEL_DIR):
    p = os.path.join(model_dir, 'scaler.npz')
    if not os.path.exists(p):
        return None
    try:
        data = np.load(p)
        return {'mean': data['mean'], 'std': data['std']}
    except Exception:
        return None

def apply_scaler(X, scaler):
    if scaler is None:
        return X
    return (np.asarray(X, dtype=np.float32) - scaler['mean']) / scaler['std']

def estimate_kp_from_inputs(inputs: list) -> float:
    """Infer a proxy Kp value from solar activity when Kp is unavailable."""
    try:
        solar = float(inputs[0]) if len(inputs) > 0 else 5.0
        return float(clamp((solar - 4.0) * 0.5 + 3.0, 0.0, 9.0, 3.0))
    except Exception:
        return 3.0

def uncertainty_confidence_pct(std, bounds=None):
    if std is None:
        return None
    bounds = bounds or PHYSICAL_OUTPUT_BOUNDS
    spans = np.array([hi - lo for lo, hi in bounds], dtype=np.float64)
    spans[spans == 0] = 1.0
    std_arr = np.abs(np.asarray(std, dtype=np.float64).flatten())
    if std_arr.shape[0] != spans.shape[0]:

        spans = np.full_like(std_arr, float(np.mean(spans)))
    rel = std_arr / spans
    pct = 99.0 * np.exp(-rel / 0.065)
    return np.clip(pct, 25.0, 99.0).tolist()

def combined_confidence_pct(std, prediction: dict, inputs: list, lat=None, lon=None, local_time=None, channel_order=None) -> dict:
    """UQ plus physics plausibility."""
    phys_pct = 100.0 * plausibility_score(prediction, inputs, lat=lat, lon=lon, local_time=local_time)
    model_pcts = uncertainty_confidence_pct(std)
    order = channel_order or CORE_FEATURE_NAMES

    try:
        blend_w = get_channel_blend_weights()
    except Exception:
        blend_w = [DEFAULT_ML_BLEND_WEIGHT] * NUM_CORE_FEATURES
    if model_pcts is None:
        per_channel = {order[i]: round(phys_pct, 1) for i in range(len(order))}
        return {'overall_pct': round(phys_pct, 1), 'per_channel_pct': per_channel,
                'basis': 'physics_plausibility_only', 'model_uncertainty_available': False,
                'channel_ml_blend_weights': {order[i]: float(blend_w[i]) for i in range(min(len(order), len(blend_w)))}}
    per_channel = {}
    for i in range(min(len(order), len(model_pcts))):
        w_ml = float(blend_w[i]) if i < len(blend_w) else float(DEFAULT_ML_BLEND_WEIGHT)

        if w_ml <= 0.05:
            per_channel[order[i]] = round(max(80.0, min(96.0, 0.25 * phys_pct + 0.75 * 90.0)), 1)
            continue

        model_mix = 0.65 * w_ml
        phys_mix = 1.0 - model_mix
        per_channel[order[i]] = round(model_mix * model_pcts[i] + phys_mix * phys_pct, 1)
    overall = round(float(np.mean(list(per_channel.values()))), 1) if per_channel else round(phys_pct, 1)
    return {'overall_pct': overall, 'per_channel_pct': per_channel,
            'basis': 'mc_dropout_plus_physics_blend_aware', 'model_uncertainty_available': True,
            'channel_ml_blend_weights': {order[i]: float(blend_w[i]) for i in range(min(len(order), len(blend_w)))}}

def plausibility_score(prediction: dict, inputs: list, lat=None, lon=None, local_time=None) -> float:
    """Distance from physics anchors."""
    score = 1.0
    if local_time is not None and lat is not None and lon is not None:
        phys_temp = physics_temperature(lat, lon, local_time)
        diff = abs(float(prediction.get('temperature', phys_temp)) - phys_temp)
        score -= min(0.5, diff / 80.0)
    kp_proxy = estimate_kp_from_inputs(inputs)
    phys_rad = physics_radiation(
        solar_activity=inputs[0], kp=kp_proxy,
        proton_flux=float(prediction.get('radiation', inputs[1])),
    )
    pred_rad = float(prediction.get('radiation', phys_rad))
    diff_rad = abs(pred_rad - phys_rad)

    score -= min(0.35, diff_rad / 0.25)
    return float(clamp(score, 0.0, 1.0, 0.0))

def long_term_forecast(inputs, horizon=7, physics_weight=DEFAULT_ML_BLEND_WEIGHT, use_ensemble=False, lat=None, lon=None, local_time=None, extra=None):
    results = []
    current = list(inputs)
    hour = float(local_time) if local_time is not None else 12.0
    for day in range(horizon):
        step_time = (hour + 24.0 * day) % 24.0
        forecast = hybrid_forecast(current, lat=lat, lon=lon, local_time=step_time, physics_weight=physics_weight, use_ensemble=use_ensemble, extra=extra)
        hybrid = forecast['hybrid'] if isinstance(forecast, dict) and 'hybrid' in forecast else forecast
        results.append({
            'day': day + 1,
            'forecast': hybrid,
            'plausibility': plausibility_score(hybrid, current, lat=lat, lon=lon, local_time=step_time)
        })
        current = [hybrid['solar'], hybrid['radiation'], hybrid['temperature'], hybrid['moonquakes'], hybrid['micrometeorites'], hybrid['dust']]
    return {'long_term': results}

def estimate_kp_proxy(solar_activity: float, radiation: float) -> float:

    try:
        if solar_activity > 15.0:
            return 8.0
        if solar_activity > 10.0:
            return 6.0
        return float(clamp((solar_activity - 4.0) * 0.5 + 3.0, 0.0, 9.0, 3.0))
    except Exception:
        return 3.0

def hybrid_forecast(inputs, lat=None, lon=None, local_time=None, physics_weight=DEFAULT_ML_BLEND_WEIGHT, use_ensemble=False, extra=None):
    refined = refine_prediction(
        inputs, lat=lat, lon=lon, local_time=local_time,
        physics_weight=physics_weight, use_ensemble=use_ensemble, extra=extra,
    )
    return {
        'hybrid': refined['hybrid'],
        'physics': refined.get('physics'),
        'ml': refined.get('ml'),
        'plausibility': refined.get('plausibility'),
        'blend_weights': refined.get('blend_weights'),
        'regime': refined.get('regime'),
        'confidence': refined.get('confidence'),
    }

app = Flask(__name__, static_folder='.', static_url_path='')

_STATIC_BLOCKLIST_PREFIXES = ('data/', 'saved_model', 'scripts/', '.venv', '.git', '.devin', '__pycache__')
_STATIC_BLOCKLIST_SUFFIXES = ('.py', '.env', '.pyc', '.log')

@app.before_request
def _guard_static_paths():
    p = request.path.lstrip('/')
    if p.startswith(_STATIC_BLOCKLIST_PREFIXES) or p.endswith(_STATIC_BLOCKLIST_SUFFIXES):
        return jsonify({'error': 'not found'}), 404

@app.route('/')
def index():
    return app.send_static_file('landing.html')

@app.route('/client-token')
def client_token():
    token = os.getenv('CESIUM_ION_TOKEN', '')
    return jsonify({'token': token})

_EXTENDED_FEATURE_PAYLOAD_KEYS = (
    'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index',
    'regolith_depth', 'thermal_inertia',
    'hour_of_day', 'day_of_month', 'month_of_year'
)

def _extra_features_from_payload(payload):
    return {k: payload[k] for k in _EXTENDED_FEATURE_PAYLOAD_KEYS if k in payload}

def _locked_physics_weight(payload):
    requested = payload.get('physics_weight')
    locked = float(DEFAULT_ML_BLEND_WEIGHT)
    overridden = requested is not None and float(requested) != locked
    return locked, overridden

@app.route('/predict', methods=['POST'])
def predict_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error':'invalid payload'}), 400
    inputs = payload.get('input') or payload.get('inputs')
    if inputs is None or len(inputs) != 6:
        return jsonify({'error':'`input` must be an array of 6 numeric values'}), 400

    lat = payload.get('lat')
    lon = payload.get('lon')
    local_time = payload.get('local_time')
    physics_weight, weight_overridden = _locked_physics_weight(payload)
    use_ensemble = bool(payload.get('use_ensemble', False))
    extra = _extra_features_from_payload(payload)

    try:
        fast = physics_estimate(inputs, lat=lat, lon=lon, local_time=local_time)
        refined = refine_prediction(inputs, lat=lat, lon=lon, local_time=local_time, physics_weight=physics_weight, use_ensemble=use_ensemble, extra=extra)
        response = {
            'fast_estimate': fast,
            'refined_estimate': refined.get('hybrid') if refined else None,
            'physics_estimate': refined.get('physics') if refined else fast,
            'ml_estimate': refined.get('ml') if refined else None,
            'plausibility': refined.get('plausibility') if refined else plausibility_score(fast, inputs, lat=lat, lon=lon, local_time=local_time),
            'confidence': refined.get('confidence') if refined else None,
            'physics_weight': physics_weight
        }
        response['prediction'] = response['refined_estimate'] or response['fast_estimate']
        if refined and refined.get('ml') is None:
            response['note'] = 'Model unavailable; returning physics-based estimate.'
        if weight_overridden:
            response['physics_weight_note'] = f'physics_weight is locked to {physics_weight}; requested override was ignored.'
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/forecast/hybrid', methods=['POST'])
def hybrid_forecast_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error':'invalid payload'}), 400
    inputs = payload.get('input') or payload.get('inputs')
    if inputs is None or len(inputs) != 6:
        return jsonify({'error':'`input` must be an array of 6 numeric values'}), 400
    lat = payload.get('lat')
    lon = payload.get('lon')
    local_time = payload.get('local_time')
    physics_weight, weight_overridden = _locked_physics_weight(payload)
    use_ensemble = bool(payload.get('use_ensemble', False))
    extra = _extra_features_from_payload(payload)
    try:
        horizon = int(payload.get('horizon', 1))
        if horizon > 1:
            result = long_term_forecast(inputs, horizon=horizon, physics_weight=physics_weight, use_ensemble=use_ensemble, lat=lat, lon=lon, local_time=local_time, extra=extra)
        else:
            result = hybrid_forecast(inputs, lat=lat, lon=lon, local_time=local_time, physics_weight=physics_weight, use_ensemble=use_ensemble, extra=extra)
        result['physics_weight'] = physics_weight
        if weight_overridden:
            result['physics_weight_note'] = f'physics_weight is locked to {physics_weight}; requested override was ignored.'
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/forecast/long_term', methods=['POST'])
def long_term_forecast_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error':'invalid payload'}), 400
    inputs = payload.get('input') or payload.get('inputs')
    if inputs is None or len(inputs) != 6:
        return jsonify({'error':'`input` must be an array of 6 numeric values'}), 400
    lat = payload.get('lat')
    lon = payload.get('lon')
    local_time = payload.get('local_time')
    physics_weight, weight_overridden = _locked_physics_weight(payload)
    use_ensemble = bool(payload.get('use_ensemble', False))
    horizon = int(payload.get('horizon', 7))
    extra = _extra_features_from_payload(payload)
    try:
        result = long_term_forecast(inputs, horizon=horizon, physics_weight=physics_weight, use_ensemble=use_ensemble, lat=lat, lon=lon, local_time=local_time, extra=extra)
        result['physics_weight'] = physics_weight
        if weight_overridden:
            result['physics_weight_note'] = f'physics_weight is locked to {physics_weight}; requested override was ignored.'
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/train/metrics', methods=['GET'])
def train_metrics_endpoint():
    return jsonify({'last_training_metrics': _LAST_TRAINING_METRICS, 'model_loaded': _MODEL is not None, 'ensemble_count': len(_ENSEMBLE)})

@app.route('/train', methods=['POST'])
def train_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error': 'invalid payload'}), 400

    training = payload.get('data')
    csv_path = payload.get('csv_path')
    if training is None and csv_path is None:
        return jsonify({'error': 'provide `data` or `csv_path` to train'}), 400

    try:
        allow_same_targets = bool(payload.get('allow_input_targets', False))
        if csv_path:

            X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=allow_same_targets)
            Xt = X_df.values
            Yt = Y_df.values
        else:
            arr = np.array(training, dtype=np.float32)

            if arr.ndim != 2 or arr.shape[1] < 6:
                return jsonify({'error': 'training rows must contain at least 6 columns'}), 400

            if arr.shape[1] == 6:
                if not allow_same_targets:
                    return jsonify({'error': 'When training from raw inputs only, set allow_input_targets=true to confirm targets == inputs'}), 400
                Xt = arr
                Yt = arr
            elif arr.shape[1] == NUM_EXPANDED_FEATURES + 6:
                Xt = arr[:, :NUM_EXPANDED_FEATURES]
                Yt = arr[:, NUM_EXPANDED_FEATURES:NUM_EXPANDED_FEATURES + 6]
            else:
                Xt = arr[:, :6]
                Yt = arr[:, 6:12] if arr.shape[1] >= 12 else arr[:, :6]

        Xt = np.asarray(Xt, dtype=np.float32)
        Yt = np.asarray(Yt, dtype=np.float32)
        n_samples = int(Xt.shape[0])
        if n_samples < 6:
            return jsonify({'error': 'not enough samples to train; need at least 6 rows'}), 400

        if Xt.shape[1] != NUM_EXPANDED_FEATURES:
            Xt = np.stack([build_expanded_features(row) for row in Xt], axis=0)

        mean = Xt.mean(axis=0)
        std = Xt.std(axis=0)
        std[std==0] = 1.0
        Xt = (Xt - mean) / std

        n_features = int(Xt.shape[1])
        min_rows_for_window = SEQUENCE_LENGTH + 10
        use_temporal = n_samples >= min_rows_for_window
        if use_temporal:
            Xt_windows, Yt_windows = make_sliding_windows(Xt, Yt, sequence_length=SEQUENCE_LENGTH)
        else:
            Xt_windows, Yt_windows = Xt, Yt
        n_fit_samples = int(Xt_windows.shape[0])

        X_cal = Y_cal = None
        if n_fit_samples >= 20:
            n_cal = min(max(4, int(round(n_fit_samples * 0.15))), n_fit_samples - 4)
            if n_cal > 0:
                X_fit, Y_fit = Xt_windows[:-n_cal], Yt_windows[:-n_cal]
                X_cal, Y_cal = Xt_windows[-n_cal:], Yt_windows[-n_cal:]
            else:
                X_fit, Y_fit = Xt_windows, Yt_windows
        else:
            X_fit, Y_fit = Xt_windows, Yt_windows
        n_fit = int(X_fit.shape[0])

        global _MODEL, _LAST_TRAINING_METRICS, _CALIBRATION
        with _MODEL_LOCK:
            if use_temporal:
                _MODEL = build_temporal_model(sequence_length=SEQUENCE_LENGTH, num_features=n_features)
            elif n_features != 6:
                _MODEL = build_model(input_shape=(n_features,))
            else:
                _MODEL = build_simple_model()

            if n_fit < 20:
                val_split = 0.0
            else:
                val_split = float(payload.get('validation_split', 0.15))

            epochs = int(payload.get('epochs', 200))
            batch_size = int(payload.get('batch_size', 16))

            callbacks = []
            try:
                es = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=12, restore_best_weights=True)
                callbacks.append(es)
            except Exception:
                pass

            os.makedirs(MODEL_DIR, exist_ok=True)
            try:
                mc = tf.keras.callbacks.ModelCheckpoint(BEST_MODEL_FILE, save_best_only=True, monitor='val_loss')
                callbacks.append(mc)
            except Exception:
                pass

            history = None
            try:
                if val_split > 0.0:
                    history = _MODEL.fit(X_fit, Y_fit, epochs=epochs, batch_size=batch_size, validation_split=val_split, shuffle=True, callbacks=callbacks, verbose=1)
                else:
                    history = _MODEL.fit(X_fit, Y_fit, epochs=max(10, min(epochs, 100)), batch_size=max(4, batch_size), shuffle=True, callbacks=callbacks, verbose=1)
            except Exception as e:
                return jsonify({'error': f'training failed: {str(e)}'}), 500

            try:
                save_keras_model(_MODEL, MODEL_DIR)
            except Exception:
                try:
                    _MODEL.save_weights(os.path.join(MODEL_DIR, 'weights.h5'))
                except Exception:
                    pass

            try:
                np.savez(os.path.join(MODEL_DIR, 'scaler.npz'), mean=mean, std=std)
                global _SCALER
                _SCALER = {'mean': mean, 'std': std}
            except Exception:
                pass

            calibration_info = {'fitted': False}
            if X_cal is not None and len(X_cal) > 0:
                try:
                    raw_cal_preds = _MODEL.predict(X_cal, verbose=0)
                    calib_method = payload.get('calibration_method', 'platt')
                    calib = fit_calibration(raw_cal_preds, Y_cal, method=calib_method)
                    save_calibration(calib, MODEL_DIR)
                    _CALIBRATION = calib
                    calibration_info = {'fitted': True, 'method': calib.get('method'), 'rows': int(len(X_cal))}
                except Exception as e:
                    calibration_info = {'fitted': False, 'error': str(e)}

            if history is not None and hasattr(history, 'history'):
                _LAST_TRAINING_METRICS = {k: float(v[-1]) for k, v in history.history.items() if len(v) > 0}

        return jsonify({
            'status': 'trained',
            'rows': int(n_samples),
            'input_features': n_features,
            'temporal': use_temporal,
            'sequence_length': SEQUENCE_LENGTH if use_temporal else None,
            'fit_samples': n_fit,
            'calibration': calibration_info,
            'metrics': _LAST_TRAINING_METRICS
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ensemble/train', methods=['POST'])
@require_api_key
def ensemble_train_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error':'invalid payload'}), 400
    training = payload.get('data')
    csv_path = payload.get('csv_path')
    n_models = int(payload.get('n_models', 3))
    epochs = int(payload.get('epochs', 50))
    try:
        if csv_path:
            X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=bool(payload.get('allow_input_targets', False)))
            Xt = X_df.values
            Yt = Y_df.values
        elif training is not None:
            arr = np.array(training, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < 6:
                return jsonify({'error':'training rows invalid'}), 400
            Xt = arr[:, :6] if arr.shape[1] >= 6 else arr
            Yt = arr[:, 6:12] if arr.shape[1] >= 12 else arr[:, :6]
        else:
            return jsonify({'error':'provide data or csv_path'}), 400

        mean = Xt.mean(axis=0)
        std = Xt.std(axis=0)
        std[std==0] = 1.0
        np.savez(os.path.join(MODEL_DIR, 'scaler.npz'), mean=mean, std=std)

        Xs = (Xt - mean) / std

        paths = train_ensemble(Xs, Yt, n_models=n_models, epochs=epochs)

        global _ENSEMBLE, _SCALER, _LAST_TRAINING_METRICS
        _ENSEMBLE = load_ensemble()
        _SCALER = load_scaler()
        _LAST_TRAINING_METRICS = {'ensemble_models': len(_ENSEMBLE), 'epochs': epochs, 'trained_at': int(time.time())}
        return jsonify({'status':'ensemble_trained','models': len(_ENSEMBLE), 'paths': paths, 'metrics': _LAST_TRAINING_METRICS})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/calibrate', methods=['POST'])
@require_api_key
def calibrate_endpoint():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error': 'invalid payload'}), 400
    method = payload.get('method', 'platt')
    training = payload.get('data')
    csv_path = payload.get('csv_path')

    try:
        if csv_path:
            X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=bool(payload.get('allow_input_targets', False)))
            Xt = np.stack([build_expanded_features(row) for row in X_df.values], axis=0)
            Yt = Y_df.values.astype(np.float32)
        elif training is not None:
            arr = np.array(training, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < NUM_CORE_FEATURES + 6:
                return jsonify({'error': f'each row must have at least {NUM_CORE_FEATURES + 6} columns (features + 6 targets)'}), 400
            n_feat = arr.shape[1] - 6
            Xt = arr[:, :n_feat]
            if Xt.shape[1] != NUM_EXPANDED_FEATURES:
                Xt = np.stack([build_expanded_features(row) for row in Xt], axis=0)
            Yt = arr[:, n_feat:n_feat + 6]
        else:
            return jsonify({'error': 'provide `data` or `csv_path`'}), 400

        global _MODEL, _SCALER, _CALIBRATION
        model = _MODEL
        if model is None:
            return jsonify({'error': 'no trained model loaded; train a model before calibrating'}), 400

        if _SCALER is not None and _SCALER['mean'].shape[0] == Xt.shape[1]:
            Xs = apply_scaler(Xt, _SCALER)
        else:
            Xs = Xt

        input_shape = model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]

        if len(input_shape) == 3:
            seq_len = input_shape[1] or SEQUENCE_LENGTH
            if Xs.shape[0] < seq_len:
                return jsonify({'error': f'need at least {seq_len} rows to calibrate a temporal model'}), 400
            Xs_seq, Y_for_calib = make_sliding_windows(Xs, Yt, sequence_length=seq_len)
            raw_preds = model.predict(Xs_seq, verbose=0)
        else:
            raw_preds = model.predict(Xs, verbose=0)
            Y_for_calib = Yt

        calib = fit_calibration(raw_preds, Y_for_calib, method=method)
        save_calibration(calib, MODEL_DIR)
        _CALIBRATION = calib
        return jsonify({'status': 'calibrated', 'method': calib.get('method'), 'rows': int(Y_for_calib.shape[0])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/batch_ingest', methods=['POST'])
@require_api_key
def batch_ingest_endpoint():
    if not request.is_json:
        return jsonify({'error':'send JSON body with sources'}), 400
    payload = request.get_json(force=True)
    try:
        out = batch_ingest_from_sources(payload, out_dir=payload.get('out_dir','data/ingested'))
        return jsonify({'status':'ok','files': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_sources', methods=['GET'])
@require_api_key
def fetch_sources_endpoint():
    start = request.args.get('start')
    end = request.args.get('end')
    api_key = request.args.get('api_key') or os.environ.get('NASA_KEY', 'DEMO_KEY')
    try:
        data = fetch_real_source_data(start_date=start, end_date=end, nasa_key=api_key)
        return jsonify({'status': 'ok', 'sources': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data', methods=['GET'])
def data_endpoint():

    return jsonify({'real_time': real_time_data, 'historical': historical_data, 'radiation_cache': radiation_cache})

@app.route('/train/schema', methods=['GET'])
def train_schema_endpoint():
    return jsonify({
        'columns': get_training_columns(),
        'example': get_schema_example(),
        'description': 'A 12-column CSV with 6 input features and 6 target values. Set allow_input_targets=true if you are training with input==target rows.'
    })

@app.route('/status', methods=['GET'])
def status_endpoint():

    model_input_shape = None
    is_temporal = None
    if _MODEL is not None:
        try:
            shape = _MODEL.input_shape
            if isinstance(shape, list):
                shape = shape[0]
            model_input_shape = list(shape)
            is_temporal = len(shape) == 3
        except Exception:
            pass
    return jsonify({
        'model_loaded': _MODEL is not None,
        'model_available': os.path.isdir(MODEL_DIR),
        'model_dir': MODEL_DIR,
        'model_input_shape': model_input_shape,
        'model_is_temporal': is_temporal,
        'sequence_length': SEQUENCE_LENGTH,
        'num_expanded_features': NUM_EXPANDED_FEATURES,
        'calibration_loaded': _CALIBRATION is not None,
        'calibration_method': _CALIBRATION.get('method') if _CALIBRATION else None,
        'ensemble_count': len(_ENSEMBLE),
        'real_time_timestamp': real_time_data.get('timestamp'),
        'historical_loaded': bool(historical_data)
    })

@app.route('/ingest', methods=['POST'])
@require_api_key
def ingest_endpoint():
    try:

        payload = None
        if request.is_json:
            payload = request.get_json(force=True)

        donki = payload.get('donki') if payload else None
        noaa = payload.get('noaa') if payload else None
        diviner = payload.get('diviner') if payload else None
        apollo = payload.get('apollo') if payload else None
        mem3 = payload.get('mem3') if payload else None
        ldex = payload.get('ldex') if payload else None
        crater = payload.get('crater') if payload else None

        df = build_training_dataset(donki=donki, noaa=noaa, diviner=diviner, crater=crater, ldex=ldex, apollo=apollo, mem3=mem3)
        out_dir = os.path.join('data', 'ingested')
        os.makedirs(out_dir, exist_ok=True)
        ts = int(time.time())
        csv_path = os.path.join(out_dir, f'training_{ts}.csv')
        save_dataset(csv_path, df)
        return jsonify({'status':'ok','rows': int(df.shape[0]), 'csv': csv_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/validate', methods=['POST'])
@require_api_key
def validate_endpoint():
    try:
        if not request.is_json:
            return jsonify({'error':'send JSON body with `csv_path`'}), 400
        payload = request.get_json(force=True)
        csv_path = payload.get('csv_path')
        if not csv_path:
            return jsonify({'error':'provide `csv_path` in JSON body'}), 400
        X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=bool(payload.get('allow_input_targets', False)))
        return jsonify({'valid': True, 'rows': int(X_df.shape[0])})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 400

if __name__ == '__main__':
    updater = threading.Thread(target=background_updater, args=(900,), daemon=True)
    updater.start()

    ok = init_surrogate(n_samples=384)
    if ok:
        print('Initialized fast linear surrogate predictor (instant warmup).')
    else:
        print('Surrogate initialization failed; physics-only fallback will be used.')

    def load_model_background():
        global _MODEL, _ENSEMBLE, _SCALER, _CALIBRATION
        try:
            m = load_saved_model(MODEL_DIR)
            if m is not None:
                _MODEL = m
                print('Loaded saved model from', MODEL_DIR)
            else:
                print('No saved model found on disk; will continue with surrogate/physics.')
        except Exception as e:
            print('Model background load failed:', e)
        try:
            _ENSEMBLE = load_ensemble()
            if _ENSEMBLE:
                print(f'Loaded ensemble with {len(_ENSEMBLE)} models')
        except Exception:
            pass
        try:
            _SCALER = load_scaler()
            if _SCALER is not None:
                print('Loaded input scaler from saved_model/scaler.npz')
        except Exception:
            pass
        try:
            _CALIBRATION = load_calibration(MODEL_DIR)
            if _CALIBRATION is not None:
                print(f"Loaded output calibration pass (method={_CALIBRATION.get('method')})")
        except Exception:
            pass

    loader = threading.Thread(target=load_model_background, daemon=True)
    loader.start()

    print('Server ready; starting Flask on http://127.0.0.1:5000')
    app.run(debug=False, host='127.0.0.1', port=5000)
