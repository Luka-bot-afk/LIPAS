from __future__ import annotations

import collections
import json
import threading
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'mercurius' / 'saved_model'
LUNAR_MODEL_DIR = ROOT / 'saved_model'

SEQUENCE_LENGTH = 72
NUM_FEATURES = 18

# Solar / heliospheric outputs only. Temperature is physics (LST + orbit), not ML.
SOLAR_FEATURE_IDX = (0, 1, 3, 4, 5)
CHANNEL_KEYS = ('solar', 'radiation', 'standoff_rm', 'p_dyn_npa', 'imf_b_mag')
OUTPUT_BOUNDS = [
    (0.0, 200.0),
    (0.0, 30.0),
    (1.00, 2.50),
    (0.0, 250.0),
    (0.0, 500.0),
]
BLEND_WEIGHTS = np.asarray([0.50, 0.45, 0.40, 0.45, 0.45], dtype=np.float64)
RIDGE_LAGS = 8
RIDGE_PATH = MODEL_DIR / 'ridge_residual.joblib'
# train_extended_model / CSV still use lunar names. Values are Mercury solar physics:
# moonquakes_per_day = magnetopause R_ss, meteor_flux_1e15 = P_dyn, dust_g_cm3 = |B|.
HAZARD_COLUMNS = (
    'solar_activity', 'radiation_mSv',
    'moonquakes_per_day', 'meteor_flux_1e15', 'dust_g_cm3',
)
TARGET_COLUMNS = (
    'target_solar_activity', 'target_radiation_mSv',
    'target_moonquakes_per_day', 'target_meteor_flux_1e15', 'target_dust_g_cm3',
)

def mercury_storm_sample_weights(Y: np.ndarray) -> np.ndarray:

    Y = np.asarray(Y, dtype=np.float64)
    w = np.ones(len(Y), dtype=np.float32)
    if Y.ndim != 2 or Y.shape[1] < 5:
        return w
    solar, rad, rss, p_dyn, bmag = Y[:, 0], Y[:, 1], Y[:, 2], Y[:, 3], Y[:, 4]
    w += 0.75 * (solar > 20.0).astype(np.float32)
    w += 1.0 * (rad > 3.0).astype(np.float32)
    w += 1.35 * (rss < 1.20).astype(np.float32)
    w += 0.85 * (p_dyn > 40.0).astype(np.float32)
    w += 0.50 * (bmag > 80.0).astype(np.float32)
    return np.clip(w, 1.0, 5.0)

def attach_next_day_targets(df, horizon: int = 1):

    if horizon < 1:
        raise ValueError('horizon must be >= 1 (same-day Y leaks identity into the LSTM)')
    out = df.sort_values(['site', 'date']).copy()
    grouped = out.groupby('site', sort=False)
    for src, tgt in zip(HAZARD_COLUMNS, TARGET_COLUMNS):
        out[tgt] = grouped[src].shift(-int(horizon))
    return out.dropna(subset=list(TARGET_COLUMNS)).reset_index(drop=True)

def persistence_rmse(df) -> float:
    x = df[list(HAZARD_COLUMNS)].to_numpy(dtype=np.float64)
    y = df[list(TARGET_COLUMNS)].to_numpy(dtype=np.float64)
    return float(np.sqrt(np.mean((x - y) ** 2)))

def mercury_custom_objects() -> dict[str, Any]:
    _install_clip_layer()
    from lipas_tf import PhysicalBoundsLayer, WeightedSum1D
    objs: dict[str, Any] = {
        'ClipToBounds': ClipToBounds,
        'mercury>ClipToBounds': ClipToBounds,
        'LastSolarUnscaled': LastSolarUnscaled,
        'mercury>LastSolarUnscaled': LastSolarUnscaled,
    }
    if PhysicalBoundsLayer is not None:
        objs['PhysicalBoundsLayer'] = PhysicalBoundsLayer
        objs['lipas>PhysicalBoundsLayer'] = PhysicalBoundsLayer
    if WeightedSum1D is not None:
        objs['WeightedSum1D'] = WeightedSum1D
    return objs

class ClipToBounds:
    """Placeholder replaced when TensorFlow is importable."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError('TensorFlow is required to build ClipToBounds')

class LastSolarUnscaled:
    """Placeholder replaced when TensorFlow is importable."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError('TensorFlow is required to build LastSolarUnscaled')

_CLIP_READY = False

def _install_clip_layer() -> None:
    global ClipToBounds, LastSolarUnscaled, _CLIP_READY
    if _CLIP_READY:
        return
    from lipas_tf import tf, layers
    if tf is None or layers is None:
        return

    @tf.keras.utils.register_keras_serializable(package='mercury')
    class _ClipToBounds(layers.Layer):
        def __init__(self, bounds, **kwargs):
            super().__init__(**kwargs)
            self.bounds = [(float(lo), float(hi)) for lo, hi in bounds]

        def build(self, input_shape):
            self.lo = tf.constant([b[0] for b in self.bounds], dtype=tf.float32)
            self.hi = tf.constant([b[1] for b in self.bounds], dtype=tf.float32)
            super().build(input_shape)

        def call(self, inputs):
            persist, residual = inputs
            return tf.clip_by_value(persist + residual, self.lo, self.hi)

        def get_config(self):
            cfg = super().get_config()
            cfg.update({'bounds': self.bounds})
            return cfg

    @tf.keras.utils.register_keras_serializable(package='mercury')
    class _LastSolarUnscaled(layers.Layer):
        def __init__(self, mean_s, std_s, idx, **kwargs):
            super().__init__(**kwargs)
            self.mean_s = [float(x) for x in mean_s]
            self.std_s = [float(x) for x in std_s]
            self.idx = [int(x) for x in idx]

        def build(self, input_shape):
            self._mean = tf.constant(self.mean_s, dtype=tf.float32)
            self._std = tf.constant(self.std_s, dtype=tf.float32)
            self._idx = tf.constant(self.idx, dtype=tf.int32)
            super().build(input_shape)

        def call(self, last):
            gathered = tf.gather(last, self._idx, axis=1)
            return gathered * self._std + self._mean

        def get_config(self):
            cfg = super().get_config()
            cfg.update({'mean_s': self.mean_s, 'std_s': self.std_s, 'idx': self.idx})
            return cfg

    ClipToBounds = _ClipToBounds
    LastSolarUnscaled = _LastSolarUnscaled
    _CLIP_READY = True

try:
    _install_clip_layer()
except Exception:
    pass

def persist_from_scaled_windows(windows: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    last = np.asarray(windows, dtype=np.float32)[:, -1, :]
    idx = np.asarray(SOLAR_FEATURE_IDX)
    mean = np.asarray(mean, dtype=np.float32)
    std = np.where(np.asarray(std, dtype=np.float32) == 0, 1.0, np.asarray(std, dtype=np.float32))
    return last[:, idx] * std[idx] + mean[idx]


def mercury_stack_features(windows: np.ndarray, mean: np.ndarray, std: np.ndarray, lags: int = RIDGE_LAGS) -> np.ndarray:
    """Last-k scaled steps plus unscaled persist / lag-1 solar residuals for Ridge."""
    Xw = np.asarray(windows, dtype=np.float32)
    mean = np.asarray(mean, dtype=np.float32)
    std = np.where(np.asarray(std, dtype=np.float32) == 0, 1.0, np.asarray(std, dtype=np.float32))
    idx = np.asarray(SOLAR_FEATURE_IDX)
    k = min(int(lags), int(Xw.shape[1]))
    lastk = Xw[:, -k:, :].reshape(len(Xw), -1)
    last = Xw[:, -1, :]
    prev = Xw[:, -2, :] if Xw.shape[1] >= 2 else last
    persist = last[:, idx] * std[idx] + mean[idx]
    persist_prev = prev[:, idx] * std[idx] + mean[idx]
    return np.concatenate([lastk, persist, persist_prev, persist - persist_prev], axis=1)


def fit_ridge_residuals(Xw: np.ndarray, Y: np.ndarray, mean: np.ndarray, std: np.ndarray, alpha: float = 3.0):
    from sklearn.linear_model import Ridge
    persist = persist_from_scaled_windows(Xw, mean, std)
    feats = mercury_stack_features(Xw, mean, std)
    models = []
    for i in range(Y.shape[1]):
        ridge = Ridge(alpha=alpha)
        ridge.fit(feats, np.asarray(Y[:, i], dtype=np.float64) - persist[:, i])
        models.append(ridge)
    return models


def ridge_predict(models, Xw: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    persist = persist_from_scaled_windows(Xw, mean, std)
    feats = mercury_stack_features(Xw, mean, std)
    pred = persist.copy()
    for i, ridge in enumerate(models):
        pred[:, i] = persist[:, i] + np.asarray(ridge.predict(feats), dtype=np.float32)
        lo, hi = OUTPUT_BOUNDS[i]
        pred[:, i] = np.clip(pred[:, i], lo, hi)
    return pred


def mix_heads_on_val(lstm: np.ndarray, ridge: np.ndarray, persist: np.ndarray, y: np.ndarray) -> list[dict]:
    """Pick a cheap persist/LSTM/Ridge mix per channel from validation RMSE."""
    grid = (0.0, 0.25, 0.5, 0.75, 1.0)
    mix = []
    for i in range(y.shape[1]):
        best = {'lstm': 1.0, 'ridge': 0.0, 'persist': 0.0, 'val_rmse': 1e9}
        for a in grid:
            for b in grid:
                if a + b > 1.0 + 1e-9:
                    continue
                c = 1.0 - a - b
                pred = a * lstm[:, i] + b * ridge[:, i] + c * persist[:, i]
                rmse = float(np.sqrt(np.mean((pred - y[:, i]) ** 2)))
                if rmse < best['val_rmse']:
                    best = {'lstm': float(a), 'ridge': float(b), 'persist': float(c), 'val_rmse': rmse}
        mix.append(best)
    return mix


def apply_channel_mix(lstm: np.ndarray, ridge: np.ndarray, persist: np.ndarray, mix: list[dict]) -> np.ndarray:
    out = np.zeros_like(persist)
    for i, w in enumerate(mix):
        out[:, i] = (
            float(w.get('lstm', 1.0)) * lstm[:, i]
            + float(w.get('ridge', 0.0)) * ridge[:, i]
            + float(w.get('persist', 0.0)) * persist[:, i]
        )
    return out


def build_mercury_solar_model(
    sequence_length: int,
    num_features: int,
    mean: np.ndarray,
    std: np.ndarray,
    lstm_units: tuple[int, ...] = (128, 64, 32),
    dense_units: tuple[int, ...] = (128, 64),
    dropout: tuple[float, ...] = (0.1, 0.1, 0.1, 0.15, 0.1),
    l2_reg: float = 1e-5,
    learning_rate: float = 1e-3,
):
    from lipas_tf import layers, models, regularizers, optimizers, tf
    if layers is None:
        raise RuntimeError('TensorFlow is required to train the Mercury solar LSTM')
    _install_clip_layer()
    idx = np.asarray(SOLAR_FEATURE_IDX, dtype=np.int32)
    mean_s = np.asarray(mean, dtype=np.float32)[idx]
    std_s = np.asarray(std, dtype=np.float32)[idx]
    std_s = np.where(std_s == 0, 1.0, std_s)

    inp = layers.Input(shape=(sequence_length, num_features), name='heliosphere_window')
    x = layers.BatchNormalization(name='input_bn')(inp)
    x = layers.LSTM(lstm_units[0], return_sequences=True, kernel_regularizer=regularizers.l2(l2_reg), name='lstm_0')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[0])(x)
    x = layers.LSTM(lstm_units[1], return_sequences=True, kernel_regularizer=regularizers.l2(l2_reg), name='lstm_1')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[1])(x)
    x = layers.LSTM(lstm_units[2], return_sequences=False, kernel_regularizer=regularizers.l2(l2_reg), name='lstm_2')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[2])(x)
    x = layers.Dense(dense_units[0], activation='relu', kernel_regularizer=regularizers.l2(l2_reg), name='dense_0')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[3])(x)
    x = layers.Dense(dense_units[1], activation='relu', kernel_regularizer=regularizers.l2(l2_reg), name='dense_1')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(dropout[4])(x)
    lstm_res = layers.Dense(
        len(CHANNEL_KEYS),
        activation=None,
        kernel_initializer=tf.keras.initializers.RandomNormal(stddev=0.01),
        bias_initializer='zeros',
        name='solar_residual',
    )(x)

    last = layers.Cropping1D(cropping=(sequence_length - 1, 0), name='last_crop')(inp)
    last = layers.Reshape((num_features,), name='last_step')(last)
    prev = layers.Cropping1D(cropping=(sequence_length - 2, 1), name='prev_crop')(inp)
    prev = layers.Reshape((num_features,), name='prev_step')(prev)
    persist = LastSolarUnscaled(mean_s, std_s, idx.tolist(), name='last_solar_unscaled')(last)
    persist_prev = LastSolarUnscaled(mean_s, std_s, idx.tolist(), name='prev_solar_unscaled')(prev)
    delta = layers.Subtract(name='solar_delta')([persist, persist_prev])
    lin_in = layers.Concatenate(name='linear_in')([persist, persist_prev, delta])
    linear_res = layers.Dense(
        len(CHANNEL_KEYS),
        kernel_initializer='zeros',
        bias_initializer='zeros',
        name='linear_residual',
    )(lin_in)
    residual = layers.Add(name='combined_residual')([linear_res, lstm_res])
    out = ClipToBounds(OUTPUT_BOUNDS, name='solar_output')([persist, residual])
    model = models.Model(inputs=inp, outputs=out, name='mercury_solar_residual_lstm')
    model.compile(
        optimizer=optimizers.Adam(learning_rate=learning_rate, clipnorm=1.0),
        loss='mse',
        metrics=['mae'],
    )
    return model

_MODEL = None
_SCALER = None
_META: dict[str, Any] | None = None
_RIDGE = None
_MIX: list[dict] | None = None
_LOCK = threading.Lock()
_HISTORY: collections.OrderedDict[str, collections.deque] = collections.OrderedDict()
_MAX_SITES = 16

def _site_key(lat: float, lon: float) -> str:
    return f'{round(float(lat), 2):.2f},{round(float(lon), 2):.2f}'

def model_ready() -> bool:
    return (MODEL_DIR / 'scaler.npz').is_file() and (
        (MODEL_DIR / 'best.keras').is_file() or (MODEL_DIR / 'model.keras').is_file()
    )

def load_mercury_model(refresh: bool = False):

    global _MODEL, _SCALER, _META, _RIDGE, _MIX
    with _LOCK:
        if _MODEL is not None and not refresh:
            return _MODEL
        if not model_ready():
            _MODEL = None
            return None
        _install_clip_layer()
        import tensorflow as tf

        objs = mercury_custom_objects()
        path = MODEL_DIR / 'best.keras'
        if not path.is_file():
            path = MODEL_DIR / 'model.keras'
        _MODEL = tf.keras.models.load_model(path, compile=False, custom_objects=objs or None)
        packed = np.load(MODEL_DIR / 'scaler.npz')
        _SCALER = {
            'mean': np.asarray(packed['mean'], dtype=np.float32),
            'std': np.asarray(packed['std'], dtype=np.float32),
        }
        packed.close()
        meta_path = MODEL_DIR / 'mercury_meta.json'
        if not meta_path.is_file():
            meta_path = MODEL_DIR / 'meta.json'
        _META = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        _RIDGE = None
        _MIX = _META.get('channel_mix') if isinstance(_META, dict) else None
        ridge_path = MODEL_DIR / 'ridge_residual.joblib'
        if ridge_path.is_file():
            try:
                import joblib
                _RIDGE = joblib.load(ridge_path)
            except Exception:
                _RIDGE = None
        if str(LUNAR_MODEL_DIR.resolve()) in str(path.resolve()):
            raise RuntimeError('Mercury LSTM refused to load lunar saved_model')
        return _MODEL

def feature_vector(phys: dict, lat: float, lon: float, lst: float, extra: dict | None = None) -> np.ndarray:
    extra = extra or {}
    sw = phys.get('wind_mercury') or {}
    vec = [
        float(phys.get('solar') or 0.0),
        float(phys.get('radiation') or 0.0),
        float(phys.get('temperature') or 0.0),
        float(phys.get('magnetopause_rm') or 1.45),
        float(phys.get('p_dyn_npa') or 0.0),
        float(sw.get('imf_b_mag') or extra.get('imf_b_mag') or 0.0),
        float(lat),
        float(lon),
        float(lst),
        float(extra.get('hour_of_day', lst)),
        float(extra.get('day_of_month', 1.0)),
        float(extra.get('month_of_year', 1.0)),
        float(extra.get('solar_wind_speed', 400.0)),
        float(extra.get('solar_wind_density', 5.0)),
        float(extra.get('imf_bz', -2.0)),
        float(extra.get('kp_index', extra.get('kp', 3.0))),
        float(phys.get('r_au') or extra.get('r_au') or 0.387),
        float(extra.get('albedo', 0.10) or 0.10) * 100.0,
    ]
    return np.asarray(vec, dtype=np.float32)

def _push_history(lat: float, lon: float, vec: np.ndarray) -> np.ndarray:
    key = _site_key(lat, lon)
    dq = _HISTORY.get(key)
    seed = np.asarray(vec, dtype=np.float32).reshape(-1)
    if dq is None:
        if len(_HISTORY) >= _MAX_SITES:
            _HISTORY.popitem(last=False)
        dq = collections.deque(maxlen=SEQUENCE_LENGTH)
        for _ in range(SEQUENCE_LENGTH):
            dq.append(seed.copy())
        _HISTORY[key] = dq
    else:
        dq.append(seed)
    return np.stack(list(dq), axis=0).astype(np.float32)

def predict_channels(phys: dict, lat: float, lon: float, lst: float, extra: dict | None = None) -> dict[str, Any] | None:
    model = load_mercury_model()
    if model is None or _SCALER is None:
        return None
    extra = extra or {}
    vec = feature_vector(phys, lat, lon, lst, extra)
    window = _push_history(lat, lon, vec)

    mean = np.asarray(_SCALER['mean'], dtype=np.float32)
    std = np.asarray(_SCALER['std'], dtype=np.float32)
    std = np.where(std == 0, 1.0, std)
    scaled = (window - mean) / std
    shape = getattr(model, 'input_shape', None)
    if isinstance(shape, list):
        shape = shape[0]
    if shape is not None and len(shape) == 2:
        x = scaled[-1:].reshape(1, -1)
    else:
        x = scaled.reshape(1, SEQUENCE_LENGTH, -1)
    raw = np.asarray(model.predict(x, verbose=0)).reshape(-1)
    if _RIDGE is not None and _MIX:
        win = scaled.reshape(1, SEQUENCE_LENGTH, -1)
        persist = persist_from_scaled_windows(win, mean, std)[0]
        ridge = ridge_predict(_RIDGE, win, mean, std)[0]
        mixed = apply_channel_mix(
            raw[:len(CHANNEL_KEYS)].reshape(1, -1),
            ridge.reshape(1, -1),
            persist.reshape(1, -1),
            _MIX,
        )[0]
        raw = mixed
    out = {}
    for i, key_ch in enumerate(CHANNEL_KEYS):
        if i < raw.shape[0]:
            lo, hi = OUTPUT_BOUNDS[i]
            out[key_ch] = float(np.clip(raw[i], lo, hi))

    out['history_frac'] = 1.0
    out['source'] = 'mercury_lstm'
    out['model_dir'] = str(MODEL_DIR)
    return out

def blend_with_physics(phys: dict, ml: dict | None) -> dict[str, float]:
    hybrid = {
        'solar': float(phys['solar']),
        'radiation': float(phys['radiation']),
        'temperature': float(phys['temperature']),
        'standoff_rm': float(phys.get('magnetopause_rm') or 1.45),
        'p_dyn_npa': float(phys.get('p_dyn_npa') or 0.0),
        'imf_b_mag': float((phys.get('wind_mercury') or {}).get('imf_b_mag') or 0.0),
    }
    if not ml:
        return hybrid
    ramp = float(ml.get('history_frac', 1.0))
    for i, key in enumerate(CHANNEL_KEYS):
        if key == 'temperature':
            continue
        w = float(BLEND_WEIGHTS[i]) * ramp
        if key in ml and w > 0:
            hybrid[key] = (1.0 - w) * hybrid[key] + w * float(ml[key])
    return hybrid
