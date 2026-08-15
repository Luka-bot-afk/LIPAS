# LIPAS

Lunar Impact and Predictive Analysis System. Hybrid ML + physics for moon space weather.

## run

```bash
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3.13 server.py
```

Then open the UI through that server (landing / dashboard html).

Important files: `space_weather_model.py`, `lunar_physics.py`, `server.py`, `data_ingestion.py`, `training_pipeline.py`. Model weights stay in local `saved_model/` (not on github).
