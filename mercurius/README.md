Mercury layer for LIPAS. Uses Parker-wind scaling of the same 1 AU feeds, plus a MESSENGER-style magnetosphere and Horizons distance.

```
python scripts/build_mercury_dataset.py
python scripts/train_mercury.py
python mercurius/scripts/fetch_horizons.py --start 2025-01-01 --end 2026-12-31
python mercurius/scripts/compare_moon_window.py
python -m unittest tests/test_mercury_physics.py
```

Moon weights stay in `saved_model/` offline. Mercury weights, if trained, go under `mercurius/saved_model/`.

© 2026 Luka Takki
