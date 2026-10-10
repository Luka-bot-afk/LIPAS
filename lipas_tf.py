"""Optional TensorFlow / Keras backend for LIPAS."""
from __future__ import annotations

from typing import Any

TF_AVAILABLE = False
tf: Any = None
layers: Any = None
models: Any = None
regularizers: Any = None
optimizers: Any = None
PhysicalBoundsLayer: Any = None
WeightedSum1D: Any = None


def _init_tensorflow() -> None:
    global TF_AVAILABLE, tf, layers, models, regularizers, optimizers
    global PhysicalBoundsLayer, WeightedSum1D

    import os

    os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

    import tensorflow as _tf
    from tensorflow.keras import layers as _layers
    from tensorflow.keras import models as _models
    from tensorflow.keras import regularizers as _regularizers
    from tensorflow.keras import optimizers as _optimizers

    try:
        _tf.config.threading.set_intra_op_parallelism_threads(1)
        _tf.config.threading.set_inter_op_parallelism_threads(1)
    except RuntimeError:
        pass

    tf = _tf
    layers = _layers
    models = _models
    regularizers = _regularizers
    optimizers = _optimizers
    TF_AVAILABLE = True

    @_tf.keras.utils.register_keras_serializable(package="lipas")
    class _PhysicalBoundsLayer(_layers.Layer):
        def __init__(self, bounds, **kwargs):
            super().__init__(**kwargs)
            self.bounds = [(float(lo), float(hi)) for lo, hi in bounds]

        def build(self, input_shape):
            self.lo = _tf.constant([b[0] for b in self.bounds], dtype=_tf.float32)
            self.span = _tf.constant([b[1] - b[0] for b in self.bounds], dtype=_tf.float32)
            super().build(input_shape)

        def call(self, inputs):
            return self.lo + self.span * _tf.sigmoid(inputs)

        def get_config(self):
            config = super().get_config()
            config.update({"bounds": self.bounds})
            return config

    @_tf.keras.utils.register_keras_serializable(package="lipas")
    class _WeightedSum1D(_layers.Layer):
        def call(self, inputs):
            return _tf.reduce_sum(inputs, axis=1)

        def compute_output_shape(self, input_shape):
            return (input_shape[0], input_shape[2])

    PhysicalBoundsLayer = _PhysicalBoundsLayer
    WeightedSum1D = _WeightedSum1D


try:
    _init_tensorflow()
except Exception:
    pass
