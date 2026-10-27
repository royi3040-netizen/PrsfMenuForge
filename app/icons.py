"""Original, resolution-independent SVG icons for PrsfMenuForge.
No icon fonts or runtime network dependencies.
"""
from __future__ import annotations
from pathlib import Path

# Each shape is an original simple stroke-based SVG assembled locally.
PATHS: dict[str, str] = {
    'logo': '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M8 15l4-8 4 8M9.6 12h4.8"/>',
    'mouse': '<rect x="6" y="2" width="12" height="20" rx="6"/><path d="M12 2v8m-6 2h12"/>',
    'grid': '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    'monitor': '<rect x="2" y="4" width="20" height="14" rx="2"/><path d="M8 22h8m-4-4v4"/>',
    'folder': '<path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v10H3z"/>',
    'file': '<path d="M6 2h8l5 5v15H6zM14 2v5h5M9 12h6m-6 4h6"/>',
    'drive': '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 8h.1M7 17h.1"/>',
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M16 16l5 5"/>',
    'refresh': '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9A8 8 0 0119 7m-.5 8A8 8 0 015 17"/>',
    'plus': '<path d="M12 4v16M4 12h16"/>',
    'eye': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    'eye-off': '<path d="M3 3l18 18M10 5.2A11.8 11.8 0 0112 5c6 0 10 7 10 7a17.8 17.8 0 01-3.8 4.5M6 6.5A18 18 0 002 12s4 7 10 7c1 0 2-.2 3-.5"/><path d="M10 10a3 3 0 004 4"/>',
    'trash': '<path d="M4 7h16M9 7V4h6v3m-9 0 1 14h10l1-14M10 11v6m4-6v6"/>',
    'shield': '<path d="M12 2l9 4v6c0 6-4 9-9 11-5-2-9-5-9-11V6z"/><path d="M8 12l3 3 5-6"/>',
    'gear': '<circle cx="12" cy="12" r="3"/><path d="M10 2h4l.7 2.8 2.5 1.4 2.8-.9 2 3.5-2.1 2.1v2.4l2.1 2.1-2 3.5-2.8-.9-2.5 1.4L14 22h-4l-.7-2.8-2.5-1.4-2.8.9-2-3.5 2.1-2.1v-2.4L2 8.6l2-3.5 2.8.9 2.5-1.4z"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.5 1.5m11.2 11.2 1.5 1.5M19.1 4.9l-1.5 1.5M6.4 17.6l-1.5 1.5"/>',
    'moon': '<path d="M20 15A8.5 8.5 0 019 4a8.5 8.5 0 1011 11z"/>',
    'globe': '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a16 16 0 010 20M12 2a16 16 0 000 20"/>',
    'layout': '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M10 3v18m0-12h12"/>',
    'backup': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3h8M8 14h8m-4-3v6"/>',
    'info': '<circle cx="12" cy="12" r="10"/><path d="M12 11v6m0-10v.5"/>',
    'puzzle': '<path d="M4 4h5a3 3 0 016 0h5v5a3 3 0 010 6v5h-5a3 3 0 01-6 0H4v-5a3 3 0 010-6z"/>',
    'lock': '<rect x="5" y="11" width="14" height="11" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    'chevron': '<path d="M9 18l6-6-6-6"/>',
    'check': '<path d="M4 12l5 5L20 6"/>',
    'alert': '<path d="M12 3L2 21h20zM12 9v5m0 4v.1"/>',
    'folder-open': '<path d="M3 18V6a2 2 0 012-2h5l2 2h7a2 2 0 012 2v3M3 20l4-9h15l-4 9z"/>',
    'external': '<path d="M13 4h7v7M20 4l-9 9M20 14v6H4V4h6"/>',
}


def svg_data(name: str, color: str = '#77A6EA', size: int = 24) -> bytes:
    inner = PATHS.get(name, PATHS['file'])
    data = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')
    return data.encode('utf-8')


def save_assets(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in PATHS:
        (destination / f'{name}.svg').write_bytes(svg_data(name))
