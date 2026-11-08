#!/usr/bin/env python3
"""Run a script on CPU-only TF (Metal left for T4c). Usage: run_on_cpu.py script.py [args...]"""
from __future__ import annotations
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import cpu_tf_bootstrap  # noqa: F401

if len(sys.argv) < 2:
    raise SystemExit('usage: run_on_cpu.py script.py [args...]')
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name='__main__')
