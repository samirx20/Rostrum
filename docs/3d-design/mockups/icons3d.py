"""3D line icons for the Rostrum3D mockups (18 x 18 viewBox). Falls back to the shared 2D set (icons.py, copied from 2D)."""
from icons import icon as icon2d

SW = 'fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"'
P = {
    "move": f'<path d="M9 2v14M2 9h14M9 2l-2 2M9 2l2 2M9 16l-2-2M9 16l2-2M2 9l2-2M2 9l2 2M16 9l-2-2M16 9l-2 2" {SW}/>',
    "rotate": f'<path d="M14.5 6.5A6 6 0 1 0 15 11" {SW}/><path d="M15 3v4h-4" {SW}/>',
    "scale": f'<rect x="2.5" y="8.5" width="7" height="7" {SW}/><path d="M9 9l6.5-6.5M11 2.5h4.5V7" {SW}/>',
    "cube": f'<path d="M9 2l6.5 3.5v7L9 16l-6.5-3.5v-7zM2.5 5.5L9 9l6.5-3.5M9 9v7" {SW}/>',
    "sphere": f'<circle cx="9" cy="9" r="6.5" {SW}/><ellipse cx="9" cy="9" rx="6.5" ry="2.4" {SW}/>',
    "cylinder": f'<ellipse cx="9" cy="4.5" rx="5.5" ry="2" {SW}/><path d="M3.5 4.5v9c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-9" {SW}/>',
    "cone": f'<path d="M9 2l5.5 11.5M9 2L3.5 13.5" {SW}/><ellipse cx="9" cy="13.5" rx="5.5" ry="2" {SW}/>',
    "torus": f'<ellipse cx="9" cy="9" rx="7" ry="4.6" {SW}/><ellipse cx="9" cy="8.4" rx="2.8" ry="1.3" {SW}/>',
    "capsule": f'<rect x="5" y="2" width="8" height="14" rx="4" {SW}/>',
    "plane": f'<path d="M2 12.5l4-6h10l-4 6z" {SW}/>',
    "disc": f'<ellipse cx="9" cy="9.5" rx="7" ry="3.6" {SW}/><path d="M2 9.5v1.2c0 2 3.1 3.6 7 3.6s7-1.6 7-3.6V9.5" {SW}/>',
    "text3d": f'<path d="M3 3.5h10M8 3.5v11" stroke="{{c}}" stroke-width="1.9" stroke-linecap="round"/><path d="M13 3.5l2 1.5v0M8 14.5l2 1.5h0M10 5v11" {SW} opacity=".55"/>',
    "logo": f'<path d="M5.5 4.5A6 6 0 1 0 12.5 4.5" {SW}/><path d="M9 2v5" {SW}/><circle cx="9" cy="10" r="1.6" fill="{{c}}"/>',
    "mesh": f'<path d="M3 10l6-3 6 3-6 3z" {SW}/><path d="M9 7V2M7 4l2-2 2 2" {SW}/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="1.6" fill="{{c}}"/>' for x, y in [(3, 10), (9, 7), (15, 10), (9, 13)])
            + f'<path d="M3 10v3.5l6 3 6-3V10" {SW} opacity=".5"/>',
    "softbox": f'<path d="M3 3h12v6H3z" {SW}/><path d="M5 12l-1 3M9 12v3.5M13 12l1 3" {SW}/>',
    "strip": f'<rect x="7" y="2" width="4" height="14" rx="1" {SW}/><path d="M13.5 5v8M4.5 5v8" {SW} opacity=".6"/>',
    "spot": f'<path d="M6 2h6l-1 4H7z" {SW}/><path d="M7 6l-4 10h12L11 6" {SW} opacity=".6"/>',
    "sun": f'<circle cx="9" cy="9" r="3.2" {SW}/><path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4" {SW}/>',
    "sky": f'<path d="M2 14a7 7 0 0 1 14 0z" {SW}/><path d="M5 14a4 4 0 0 1 8 0" {SW} opacity=".55"/>',
    "card": f'<rect x="3" y="4" width="12" height="10" rx="1" {SW}/><rect x="6" y="7" width="6" height="4" fill="{{c}}" opacity=".6"/>',
    "orbit": f'<ellipse cx="9" cy="10" rx="7" ry="3.5" {SW} stroke-dasharray="2 2"/><rect x="5" y="3" width="7" height="5.5" rx="1" fill="{{c}}"/>',
    "sim": f'<circle cx="12" cy="13" r="3" {SW}/><path d="M3 3c2 0 4 3 5.5 7" {SW} stroke-dasharray="1.6 2"/>',
    "import": f'<path d="M9 2v9M5.5 7.5L9 11l3.5-3.5M2.5 11.5v3.5h13v-3.5" {SW}/>',
    "bone": f'<path d="M5.5 12.5L7 7.5l7-4-3.5 6.5z" {SW}/><circle cx="4" cy="14" r="2.2" {SW}/><circle cx="14.5" cy="3.5" r="1.4" fill="{{c}}"/>',
    "folder": f'<path d="M2 4.5h5l1.5 1.8H16v8.2H2z" {SW}/>',
    "check": f'<path d="M3.5 9.5l3.5 3.5 7.5-8" fill="none" stroke="{{c}}" stroke-width="1.8" stroke-linecap="round"/>',
    "eraser": f'<path d="M7 15.5h8M3 11.5l7-7 4.5 4.5-6.5 6.5H6.5z" {SW}/>',
    "fill": f'<path d="M4 8l5-5 6 6-5 5z" {SW}/><path d="M15.5 13.5c0 1.2-.7 2-1.5 2s-1.5-.8-1.5-2 1.5-3 1.5-3 1.5 1.8 1.5 3z" fill="{{c}}"/>',
    "picker": f'<path d="M12.5 2.5l3 3-2 2-3-3zM10.5 4.5l-7 7-.5 3.5 3.5-.5 7-7" {SW}/>',
    "film": f'<rect x="2" y="3.5" width="14" height="11" rx="1.5" {SW}/><path d="M5 3.5v11M13 3.5v11" {SW}/>',
}


def icon(name, s=18, c="currentColor"):
    if name not in P:
        return icon2d(name, s, c)
    return f'<svg width="{s}" height="{s}" viewBox="0 0 18 18">{P[name].replace("{c}", c)}</svg>'
