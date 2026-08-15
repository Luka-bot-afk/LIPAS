"""LIPAS."""
import os
import numpy as np
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, regularizers, optimizers
    TF_AVAILABLE = True
except Exception:
    tf = None
    layers = models = regularizers = optimizers = None
    TF_AVAILABLE = False

DEFAULT_ENSEMBLE_DIR = 'saved_model/ensemble'

def _build_base(input_dim: int = 6, output_dim: int = 6, dropout_rate: float = 0.2, hidden_sizes: tuple[int, ...] = (128, 128, 64)):
    if not TF_AVAILABLE:
        raise RuntimeError('TensorFlow is not available in this environment')
    inp = layers.Input(shape=(input_dim,))
    x = inp
    for size in hidden_sizes:
        x = layers.Dense(size, activation='relu', kernel_regularizer=regularizers.l2(1e-4), kernel_initializer='he_normal')(x)
        x = layers.BatchNormalization()(x)
        x = layers.Dropout(dropout_rate)(x)
    x = layers.Dense(output_dim, activation='linear')(x)
    m = models.Model(inputs=inp, outputs=x)
    m.compile(optimizer=optimizers.Adam(3e-4), loss='mse', metrics=['mae'])
    return m

def train_ensemble(X, Y, n_models=3, epochs=50, batch_size=32, ensemble_dir=DEFAULT_ENSEMBLE_DIR, patience: int = 8):
    os.makedirs(ensemble_dir, exist_ok=True)
    models_paths = []
    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)
    input_dim = X.shape[1] if X.ndim > 1 else 1
    output_dim = Y.shape[1] if Y.ndim > 1 else 1
    dataset = tf.data.Dataset.from_tensor_slices((X, Y)).shuffle(buffer_size=max(1000, len(X))).batch(batch_size)
    variants = [
        {'sizes': (128, 128, 64), 'dropout': 0.2},
        {'sizes': (192, 128, 96), 'dropout': 0.25},
        {'sizes': (256, 192, 128), 'dropout': 0.22}
    ]
    for i in range(n_models):
        tf.random.set_seed(1000 + i)
        config = variants[i % len(variants)]
        m = _build_base(input_dim=input_dim, output_dim=output_dim, dropout_rate=config['dropout'], hidden_sizes=config['sizes'])
        early = tf.keras.callbacks.EarlyStopping(monitor='loss', patience=patience, restore_best_weights=True)
        ckpt_path = os.path.join(ensemble_dir, f'model_{i}.keras')
        try:
            m.fit(dataset, epochs=epochs, callbacks=[early], verbose=1)
        except Exception:
            m.fit(X, Y, epochs=epochs, batch_size=batch_size, verbose=1)
        m.save(ckpt_path)
        models_paths.append(ckpt_path)
    np.savez(os.path.join(ensemble_dir, 'registry.npz'), paths=np.array(models_paths, dtype=object))
    return models_paths

def load_ensemble(ensemble_dir=DEFAULT_ENSEMBLE_DIR):
    reg = os.path.join(ensemble_dir, 'registry.npz')
    if not os.path.exists(reg):
        return []
    data = np.load(reg, allow_pickle=True)
    paths = data['paths'].tolist()
    custom = {}
    try:
        from space_weather_model import PhysicalBoundsLayer, WeightedSum1D
        if PhysicalBoundsLayer is not None:
            custom['PhysicalBoundsLayer'] = PhysicalBoundsLayer
        if WeightedSum1D is not None:
            custom['WeightedSum1D'] = WeightedSum1D
    except Exception:
        pass
    models = []
    for p in paths:
        try:
            models.append(tf.keras.models.load_model(p, compile=False, custom_objects=custom or None))
        except Exception:
            pass
    return models

def ensemble_predict(models, X):
    X = np.asarray(X, dtype=np.float32)
    preds = []
    for m in models:
        try:
            p = m.predict(X)
            preds.append(p)
        except Exception:
            pass
    if not preds:
        return None, None
    stacked = np.stack(preds, axis=0)
    mean = stacked.mean(axis=0)
    std = stacked.std(axis=0)
    return mean, std
