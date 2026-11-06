"""Force TensorFlow onto CPU so Metal stays free for T4c."""
from __future__ import annotations
import os
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('SETUPTOOLS_USE_DISTUTILS', 'local')
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')

# TF 2.16 on Py3.12 needs setuptools-bundled distutils
try:
    import distutils  # noqa: F401
except ModuleNotFoundError:
    try:
        import setuptools
        import setuptools._distutils as _d
        sys.modules['distutils'] = _d
    except Exception as e:
        print('cpu_tf_bootstrap: distutils shim failed', e)


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
