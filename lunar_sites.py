"""LIPAS."""
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class LunarSite:
    name: str
    lat: float
    lon: float
    terrain: str
    regolith_depth: float
    thermal_inertia: float
    albedo: float
    emissivity: float
    source: str

LUNAR_SITES: List[LunarSite] = [
    LunarSite(
        name='Apollo 11 (Mare Tranquillitatis)', lat=0.67408, lon=23.47297, terrain='mare',
        regolith_depth=4.2, thermal_inertia=48.0, albedo=0.072, emissivity=0.95,
        source='NASA coords; mare regolith ~4-5 m class; low albedo basalt.',
    ),
    LunarSite(
        name='Apollo 12 (Oceanus Procellarum)', lat=-3.01381, lon=-23.42155, terrain='mare',
        regolith_depth=4.6, thermal_inertia=49.5, albedo=0.075, emissivity=0.95,
        source='NASA coords; Procellarum mare; slightly thicker regolith estimate.',
    ),
    LunarSite(
        name='Apollo 14 (Fra Mauro)', lat=-3.6453, lon=-17.47136, terrain='highland',
        regolith_depth=10.5, thermal_inertia=56.0, albedo=0.11, emissivity=0.93,
        source='NASA coords; Fra Mauro ejecta/highland-affinity.',
    ),
    LunarSite(
        name='Apollo 15 (Hadley Rille)', lat=26.13224, lon=3.634, terrain='mare',
        regolith_depth=4.4, thermal_inertia=50.0, albedo=0.08, emissivity=0.95,
        source='NASA coords; Apollo 15 HFE heat flow 21 mW/m^2 (Langseth et al. 1976).',
    ),
    LunarSite(
        name='Apollo 16 (Descartes Highlands)', lat=-8.97341, lon=15.49859, terrain='highland',
        regolith_depth=12.5, thermal_inertia=58.5, albedo=0.13, emissivity=0.93,
        source='NASA coords; Descartes highland; thicker megaregolith affinity.',
    ),
    LunarSite(
        name='Apollo 17 (Taurus-Littrow)', lat=20.1908, lon=30.77168, terrain='mare',
        regolith_depth=4.9, thermal_inertia=52.0, albedo=0.078, emissivity=0.95,
        source='NASA coords; Apollo 17 HFE heat flow 16 mW/m^2 (Langseth et al. 1976).',
    ),
    LunarSite(
        name='Artemis III candidate - Nobile Rim 1 (south polar)', lat=-85.3, lon=31.1, terrain='polar',
        regolith_depth=3.8, thermal_inertia=42.0, albedo=0.16, emissivity=0.96,
        source='Artemis III candidate; polar cold-trap / PSR-adjacent thermal placeholder.',
    ),
    LunarSite(
        name='Shackleton crater rim vicinity (south pole)', lat=-89.9, lon=0.0, terrain='polar',
        regolith_depth=3.2, thermal_inertia=38.0, albedo=0.18, emissivity=0.97,
        source='Shackleton rim; extreme polar thermal inertia depression placeholder.',
    ),
    LunarSite(
        name='Equatorial reference (0°N, 0°E)', lat=0.0, lon=0.0, terrain='mare',
        regolith_depth=4.5, thermal_inertia=48.0, albedo=0.07, emissivity=0.95,
        source='Synthetic equatorial control at 0°N, 0°E for reproducible day/night studies.',
    ),
    LunarSite(
        name="Chang'e-4 / Statio Tianhe (Von Kármán crater, South Pole-Aitken basin, far side)",
        lat=-45.4446, lon=177.5991, terrain='mare',
        regolith_depth=5.5, thermal_inertia=51.5, albedo=0.09, emissivity=0.94,
        source='CNSA far-side landing; SPA mare-filled floor; slightly deeper regolith estimate.',
    ),
    LunarSite(
        name="Chang'e-6 (Apollo basin, far side, sample-return site)",
        lat=-41.6385, lon=-153.9852, terrain='mare',
        regolith_depth=5.2, thermal_inertia=50.5, albedo=0.085, emissivity=0.94,
        source='CNSA far-side sample-return; Apollo basin mare estimate.',
    ),
    LunarSite(
        name="Chang'e-3 (Mare Imbrium, near side)",
        lat=44.12, lon=-19.51, terrain='mare',
        regolith_depth=4.8, thermal_inertia=47.5, albedo=0.07, emissivity=0.95,
        source='CNSA mid-northern mare; Imbrium basalt optical/thermal estimate.',
    ),
    LunarSite(
        name='Statio Shiv Shakti (Chandrayaan-3 Vikram lander, high southern latitude)',
        lat=-69.373, lon=32.319, terrain='highland',
        regolith_depth=9.5, thermal_inertia=55.0, albedo=0.125, emissivity=0.93,
        source='ISRO high-southern highland; between polar and mid-lat highland classes.',
    ),
]

def get_site_names() -> List[str]:
    return [s.name for s in LUNAR_SITES]

def get_site_by_name(name: str) -> Optional[LunarSite]:
    for s in LUNAR_SITES:
        if s.name == name:
            return s
    return None

def nearest_site(lat: float, lon: float) -> LunarSite:
    best, best_d = LUNAR_SITES[0], 1e18
    for s in LUNAR_SITES:
        d = (s.lat - float(lat)) ** 2 + (s.lon - float(lon)) ** 2
        if d < best_d:
            best_d, best = d, s
    return best
