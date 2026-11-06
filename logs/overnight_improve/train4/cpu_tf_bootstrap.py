"""Force TensorFlow onto CPU so Metal stays free for T4c."""
from __future__ import annotations
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('SETUPTOOLS_USE_DISTUTILS', 'local')
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')

def force_cpu() -> None:
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        tf.config.set_visible_devices([], 'GPU')
        print('cpu_tf_bootstrap: hid GPUs', gpus)
    else:
        print('cpu_tf_bootstrap: no GPUs visible')
    print('cpu_tf_bootstrap: devices', tf.config.list_logical_devices())

force_cpu()
