from __future__ import annotations

from dataclasses import asdict, dataclass

@dataclass
class MercurySite:
    id: str
    name: str
    lat: float
    lon: float
    terrain: str
    albedo: float
    note: str
    image: str = ''
    quadrant: str = ''
    group: str = 'sites'

def _img(name: str) -> str:
    return ''

SITES = [
    MercurySite(
        'overview', 'Mercury', 0.0, 0.0, 'intercrater', 0.10,
        'All sites. Wind, heat, radiation, and the magnetic shield.',
        _img('equator'), 'overview', 'overview',
    ),

    MercurySite(
        'antipode', 'Caloris antipode', -30.0, -18.5, 'chaotic', 0.11,
        'Rough ground opposite Caloris.',
        _img('antipode'), 'antipode', 'antipodes',
    ),
    MercurySite(
        'debussy', 'Debussy', -34.0, 14.0, 'ray_crater', 0.20,
        'Bright young crater.',
        _img('debussy'), 'antipode', 'antipodes',
    ),
    MercurySite(
        'antipode_n', 'North antipode', -12.0, -25.0, 'chaotic', 0.11,
        'North of the antipode.',
        _img('antipode'), 'antipode', 'antipodes',
    ),
    MercurySite(
        'antipode_e', 'East antipode', -28.0, 8.0, 'chaotic', 0.10,
        'East of the antipode.',
        _img('antipode'), 'antipode', 'antipodes',
    ),

    MercurySite(
        'equator', 'Equator', 0.0, 0.0, 'intercrater', 0.10,
        '0°N, 0°E.',
        _img('equator'), 'E', 'sites',
    ),
    MercurySite(
        'hokusai', 'Hokusai', 58.0, 17.0, 'ray_crater', 0.18,
        'Bright crater with long rays.',
        _img('hokusai'), 'E', 'sites',
    ),
    MercurySite(
        'rachmaninoff', 'Rachmaninoff', 27.7, 57.6, 'hollows', 0.14,
        'Basin with hollows.',
        _img('rachmaninoff'), 'SE', 'sites',
    ),
    MercurySite(
        'raditladi', 'Raditladi', 27.2, 119.0, 'hollows', 0.13,
        'Basin east of Caloris.',
        _img('raditladi'), 'W', 'sites',
    ),
    MercurySite(
        'caloris', 'Caloris', 30.5, 189.8, 'smooth_plains', 0.08,
        'Largest basin.',
        _img('caloris'), 'W', 'sites',
    ),
    MercurySite(
        'tolstoj', 'Tolstoj', -16.2, -163.5, 'intercrater', 0.09,
        'Old dark basin.',
        _img('tolstoj'), 'W', 'sites',
    ),
    MercurySite(
        'beethoven', 'Beethoven', -20.8, -123.4, 'smooth_plains', 0.09,
        'Southern plains basin.',
        _img('beethoven'), 'SW', 'sites',
    ),
    MercurySite(
        'discovery', 'Discovery Rupes', -56.3, -38.3, 'tectonic', 0.10,
        'Long cliff (scarp).',
        _img('discovery'), 'SW', 'sites',
    ),
    MercurySite(
        'prokofiev', 'Prokofiev', 85.8, 62.9, 'polar', 0.12,
        'North pole ice crater.',
        _img('prokofiev'), 'N', 'sites',
    ),
    MercurySite(
        'chao', 'Chao Meng-Fu', -87.3, -132.4, 'polar', 0.12,
        'South pole ice crater.',
        _img('chao'), 'S', 'sites',
    ),
]

PHYSICS_SITES = [s for s in SITES if s.group != 'overview']
SITE_IDS = {s.id for s in SITES}

def sites_payload() -> list[dict]:
    return [asdict(s) for s in SITES]

def require_site(site_id: str) -> MercurySite:
    for s in SITES:
        if s.id == site_id:
            return s
    raise KeyError(f'unknown Mercury site {site_id!r}')

def get_site(site_id: str | None = None, name: str | None = None) -> MercurySite:
    if site_id:
        if site_id == 'overview':
            return next(s for s in SITES if s.id == 'equator')
        for s in SITES:
            if s.id == site_id:
                return s
    if name:
        n = name.lower()
        if 'overview' in n or n == 'mercury':
            return next(s for s in SITES if s.id == 'equator')
        for s in SITES:
            if s.name.lower() == n or n in s.name.lower():
                return s
    return next(s for s in SITES if s.id == 'equator')

def sites_by_quadrant() -> dict[str, list[MercurySite]]:
    out: dict[str, list[MercurySite]] = {}
    for s in SITES:
        if s.group == 'overview':
            continue
        out.setdefault(s.quadrant or 'other', []).append(s)
    return out
