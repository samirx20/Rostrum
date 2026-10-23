"""Rostrum3D design round (Team Hem, 2026-10-24): screen mockups in the same kit as Rostrum2D v2.
Layout from BRIEF.md: header 44 · icon rail 48 · viewport · settings panel 300 · bottom panel 284 (scene list 240 + keys).
Viewport pictures are real renders from the stage-2 proofs (assets/). Gizmos and outlines are SVG over the picture.
Run: python build.py   (writes every .html, then screenshots each with Edge headless; Edge is ended by PID)."""
import math, subprocess, tempfile, shutil
from pathlib import Path
from string import Template
from icons3d import icon

OUT = Path(__file__).parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ACC = "#4d8dff"
HEAD, RAIL, ROW, TL_HEAD, M = 44, 48, 28, 30, 16
PAD_L, PAD_R, GUT, FIELD_MAX, PAIR_GAP, FH_ = 12, 4, 28, 200, 4, 24
RX, GY, BZ = "#e5484d", "#46a758", "#3e8bff"


def layout(W=1646, H=900):
    """Proportional: the 1646 x 900 sizes scaled to the window (settings 280-380, bottom panel 284 at 900 high)."""
    insp = max(280, min(380, round(300 * W / 1646)))
    bottom = round(284 * H / 900)
    lcol = 220 if W < 1400 else 240
    cw, ch = W - RAIL - insp, H - HEAD - bottom
    fw = cw - 2 * M; fh = fw * 9 / 16
    if fh > ch - 2 * M:
        fh = ch - 2 * M; fw = fh * 16 / 9
    return dict(W=W, H=H, insp=insp, T=bottom, lcol=lcol, cw=cw, ch=ch, fw=fw, fh=fh)


def grid(P):
    F = int(min(FIELD_MAX, P - 140)) // 2 * 2
    return F, P - PAD_L - PAD_R - GUT - F


CSS = Template("""
*{box-sizing:border-box;margin:0;padding:0}
body{width:${W}px;height:${H}px;overflow:hidden;background:#111214;color:#e4e5e9;font:12px/1.3 'Segoe UI',system-ui,sans-serif;position:relative}
.abs{position:absolute}
.hdr{left:0;top:0;width:${W}px;height:${HEAD}px;background:#17181b;border-bottom:1px solid #26272c;display:flex;align-items:center;padding:0 10px;gap:10px}
.hdr .brand{font-weight:600;font-size:13px;color:#fff;margin-left:4px}
.hdr .crumb{color:#c9cad0;padding:4px 6px;border-radius:5px;white-space:nowrap;display:flex;align-items:center;gap:4px}
.hdr .crumb b{color:#fff;font-weight:600}
.dim{color:#80838c}
.chip{background:#222328;border:1px solid #2d2e34;border-radius:6px;padding:4px 9px;color:#c9cad0;white-space:nowrap;display:flex;align-items:center;gap:5px}
.btn{background:${ACC};color:#fff;border-radius:6px;padding:6px 14px;font-weight:600;white-space:nowrap}
.ib{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#a9abb3;flex:none}
.tabs{display:flex;background:#1e1f23;border:1px solid #2a2b30;border-radius:7px;padding:2px}
.tabs span{padding:4px 14px;border-radius:5px;color:#9a9ca4;white-space:nowrap}
.tabs span.on{background:#34363d;color:#fff;font-weight:600}
.rail{background:#17181b;border-right:1px solid #26272c;display:flex;flex-direction:column;align-items:center;padding-top:8px;gap:2px}
.tool{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#b9bbc3;position:relative}
.tool.on{background:${ACC};color:#fff}
.tool.open{background:#2b2d33;color:#fff}
.tool .more{position:absolute;right:3px;bottom:3px;border-left:4px solid transparent;border-bottom:4px solid #8d9099}
.tool.on .more{border-bottom-color:#dbe6ff}
.sep{width:24px;height:1px;background:#2c2d33;margin:5px 0}
.vp{background:#0c0d0f;overflow:hidden}
.frame{overflow:hidden;box-shadow:0 0 0 1px #000}
.frame img{width:100%;height:100%;object-fit:cover;display:block}
.insp{background:#17181b;border-left:1px solid #26272c;overflow:hidden}
.ihead{height:44px;display:flex;align-items:center;gap:8px;padding-left:${PAD_L}px;border-bottom:1px solid #25262b;white-space:nowrap}
.ihead .nm{font-size:14px;font-weight:600;color:#fff} .ihead .knd{color:#80838c;overflow:hidden;text-overflow:ellipsis}
.r{display:grid;grid-template-columns:${LC}px ${F}px ${GUT}px;height:${ROW}px;align-items:center;padding-left:${PAD_L}px}
.r .lb{color:#9a9ca4;white-space:nowrap;overflow:hidden;padding-right:8px}
.r .wide{grid-column:1 / 3}
.sh{height:${SH}px;padding:12px 0 0 ${PAD_L}px;font-size:11px;font-weight:600;color:#8d9099;border-top:1px solid #25262b;display:grid;grid-template-columns:${LCF}px ${GUT}px}
.sh.first{border-top:0}
.sh .plus{text-align:center;color:#8d9099;font-weight:400;font-size:15px;line-height:11px}
.names{border-top:1px solid #25262b;padding:9px ${PAD_L}px 0;height:36px;color:#9a9ca4;white-space:nowrap;font-size:11.5px}
.names span{color:#c9cad0;border-bottom:1px dotted #5b5e66}
.f{background:#232428;border:1px solid #2d2e34;border-radius:4px;height:${FH_}px;padding:0 7px;display:flex;align-items:center;gap:5px;color:#e4e5e9;white-space:nowrap;overflow:hidden;width:100%}
.f.act{box-shadow:0 0 0 1px ${ACC};border-color:${ACC}}
.f .u{color:#71747c} .f .k{color:#71747c;font-size:10.5px;flex:none}
.f .mx{color:#8d9099;font-style:italic}
.f .ch{margin-left:auto;display:flex}
.pair{display:grid;grid-template-columns:${HF}px ${HF}px;column-gap:${PAIR_GAP}px}
.trip{display:grid;grid-template-columns:repeat(3,1fr);column-gap:3px}
.trip .f{padding:0 5px;gap:4px}
.dia{width:9px;height:9px;transform:rotate(45deg);border:1.5px solid #5b5e66;justify-self:center}
.dia.on{background:${ACC};border-color:${ACC}}
.sw{width:14px;height:14px;border-radius:3px;flex:none;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
.ball{width:14px;height:14px;border-radius:7px;flex:none;box-shadow:inset 0 0 0 1px rgba(255,255,255,.15)}
.seg{display:flex;background:#232428;border:1px solid #2d2e34;border-radius:4px;height:${FH_}px;width:100%}
.seg span{flex:1;display:flex;align-items:center;justify-content:center;color:#9a9ca4;border-radius:3px;white-space:nowrap}
.seg span.on{background:#383a41;color:#fff}
.tg{width:28px;height:16px;border-radius:8px;background:${ACC};position:relative}
.tg:after{content:'';position:absolute;right:2px;top:2px;width:12px;height:12px;border-radius:6px;background:#fff}
.tg.off{background:#3a3c43} .tg.off:after{right:auto;left:2px}
.sl{position:relative;height:4px;border-radius:2px;background:#3a3c43;flex:1}
.sl i{position:absolute;left:0;top:0;bottom:0;border-radius:2px;background:${ACC}}
.sl b{position:absolute;top:-4px;width:12px;height:12px;border-radius:6px;background:#fff;margin-left:-6px}
.ez{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;width:100%}
.ab{background:#232428;border:1px solid #2d2e34;border-radius:5px;height:40px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:#c9cad0;font-size:10.5px}
.ab.on{background:#24314a;border-color:${ACC};color:#fff}
.bt{background:#232428;border:1px solid #2d2e34;border-radius:5px;height:${FH_}px;display:flex;align-items:center;justify-content:center;gap:5px;color:#d4d5da;white-space:nowrap;flex:1}
.bt.pri{background:${ACC};border-color:${ACC};color:#fff;font-weight:600}
.lchip{background:#262a33;border:1px solid #333a48;border-radius:11px;padding:2px 8px;color:#d4d5da;white-space:nowrap;display:inline-flex;gap:5px;align-items:center}
.lchip.off{background:transparent;border-color:#2d2e34;color:#8d9099}
.note{color:#e0b25c;font-size:11px}
.tl{background:#141518;border-top:1px solid #26272c;overflow:hidden}
.th{position:absolute;left:0;top:0;right:0;height:${TL_HEAD}px;border-bottom:1px solid #222328}
.tr{white-space:nowrap;position:absolute;left:0;top:0;width:${LCOL}px;height:${TL_HEAD}px;display:flex;align-items:center;gap:4px;padding:0 6px;border-right:1px solid #222328}
.time{font-variant-numeric:tabular-nums;color:#fff;font-weight:600;margin-left:2px}
.ruler{position:absolute;left:${LCOL}px;top:0;right:0;height:${TL_HEAD}px;color:#7d8088;font-size:10px}
.tk{position:absolute;top:2px;height:28px;border-left:1px solid #2b2c31;padding:0 0 0 4px}
.tk.mn{top:22px;height:8px;border-color:#34353b}
.lay{position:absolute;left:0;top:${TL_HEAD}px;width:${LCOL}px;bottom:0;border-right:1px solid #222328;overflow:hidden}
.lr{height:${ROW}px;display:flex;align-items:center;gap:6px;padding-right:10px;color:#c9cad0;white-space:nowrap}
.lr.sel{background:#1f2a3d;color:#fff} .lr.sub{color:#7d8088;font-size:11px}
.lr .ic{width:14px;color:#8d9099;display:flex;justify-content:center}
.lr .tw{width:12px;color:#6f727a;font-size:9px;text-align:center}
.lr .tag{margin-left:auto;color:#6f727a;font-size:11px}
.lanes{position:absolute;left:${LCOL}px;top:${TL_HEAD}px;right:0;bottom:0;overflow:hidden}
.lane{height:${ROW}px;position:relative}
.lane.sel{background:#182030}
.bar{position:absolute;top:5px;bottom:5px;border-radius:4px;background:#202125;border:1px solid #2c2d33}
.lane.sel .bar{background:#1d2a44;border-color:#2c4270}
.kd{position:absolute;top:9px;width:10px;height:10px;margin-left:-5px;transform:rotate(45deg);background:#a3a6ae}
.kd.sm{top:10px;width:8px;height:8px;margin-left:-4px}
.kd.s{background:${ACC};box-shadow:0 0 0 1.5px #cfe0ff}
.sp{position:absolute;top:4px;bottom:4px;border-radius:3px}
.sp.sel{background:rgba(77,141,255,.38);border:1px solid ${ACC}}
.eg{position:absolute;top:9px;margin-left:-6px;color:#8d9099}
.eg.s{color:#fff}
.cache{position:absolute;top:4px;bottom:4px;border-radius:3px;border:1px solid #3fae8a;color:#bfe9da;font-size:10px;padding:3px 0 0 8px;white-space:nowrap;
 background:repeating-linear-gradient(135deg,rgba(63,174,138,.30) 0 6px,rgba(63,174,138,.14) 6px 12px)}
.ph{position:absolute;top:0;bottom:0;width:1px;background:${ACC}}
.ph:before{content:'';position:absolute;left:-5px;top:2px;width:11px;height:9px;border-radius:2px;background:${ACC}}
.mk{position:absolute;top:15px;font-size:10px;color:#111;background:#f2b84b;border-radius:3px;padding:0 4px;line-height:13px;white-space:nowrap}
.mkl{position:absolute;top:0;bottom:0;width:0;border-left:1px dashed rgba(242,184,75,.45)}
.scroll{position:absolute;right:2px;width:4px;border-radius:2px;background:#3a3c43}
.fly,.pop{background:#1d1e22;border:1px solid #33353c;border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.55)}
.fly{padding:10px}
.tile{width:64px;height:62px;border-radius:7px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#c9cad0;font-size:10.5px;position:relative}
.tile.on{background:#2b2d33;color:#fff}
.tile .kk{position:absolute;right:5px;top:3px;font-size:9px;color:#6f727a}
.fh{color:#8d9099;font-size:11px;font-weight:600;margin:8px 2px 5px}
.bru{display:flex;flex-direction:column;gap:3px;width:104px;padding:4px;border-radius:6px;color:#c9cad0;font-size:10.5px}
.bru.on{background:#24314a;box-shadow:0 0 0 1px ${ACC};color:#fff}
.mono{font-family:Consolas,monospace;font-size:11px}
.qrow{display:flex;align-items:center;gap:10px;height:44px;padding:0 12px;border-bottom:1px solid #1f2024;white-space:nowrap}
.prog{height:4px;border-radius:2px;background:#2a2b30;position:relative;width:180px}
.prog i{position:absolute;left:0;top:0;bottom:0;border-radius:2px;background:${ACC}}
.thumb{width:48px;height:27px;border-radius:3px;object-fit:cover;flex:none}
.est{margin:10px ${PAD_L}px 0;padding:8px 10px;border-radius:6px;background:#1c2230;border:1px solid #2a3550;color:#dfe6f5;line-height:1.45}
""")


def css(L):
    F, LC = grid(L["insp"])
    return CSS.substitute(W=L["W"], H=L["H"], HEAD=HEAD, ACC=ACC, PAD_L=PAD_L, LC=LC, F=F, GUT=GUT, ROW=ROW, SH=ROW + 6,
                          LCF=LC + F, FH_=FH_, HF=(F - PAIR_GAP) / 2, PAIR_GAP=PAIR_GAP, TL_HEAD=TL_HEAD, LCOL=L["lcol"])


# ---------------- header and rail ----------------
def header(L, page="Build", shot="Hero 01", look="Quick", status="Saved · 4 changes"):
    narrow = L["W"] < 1400
    tabs = "".join(f'<span class="{"on" if p == page else ""}">{p}</span>' for p in ("Build", "Animate", "Render"))
    looks = "".join(f'<span class="{"on" if p == look else ""}">{p}</span>' for p in ("Quick", "Final"))
    search = (f'<div class="ib">{icon("search",15)}</div>' if narrow else
              f'<span class="chip" style="width:200px">{icon("search",13,"#80838c")}<span class="dim">Search or run a command</span></span>')
    st = "" if narrow else f'<span class="dim" style="white-space:nowrap">{status}</span>'
    return f"""<div class="abs hdr">
 <div class="ib">{icon('bars',16)}</div><span class="brand">Rostrum3D</span>
 <span class="crumb">Aurora <span class="dim">›</span> <b>{shot}</b>{icon('chev',12,'#80838c')}</span>{st}
 <div style="flex:1"></div><div class="tabs">{tabs}</div><div style="flex:1"></div>
 <div class="ib">{icon('undo',16)}</div><div class="ib">{icon('redo',16)}</div>{search}
 <span class="chip"><span class="dim">View</span> Shot camera{icon('chev',12,'#80838c')}</span>
 <div class="tabs"><span class="dim" style="padding:4px 6px 4px 8px">Look</span>{looks}</div>
 <span class="chip">Materials</span>{'' if page == 'Render' else '<span class="btn">Render</span>'}<div class="ib">{icon('help',16)}</div></div>"""


RAIL_BUILD = [("move", True), ("cube", True), ("text3d", True), ("mesh", True), ("brush", True), "|",
              ("softbox", True), ("camera", True), ("sim", True), "|", ("import", True)]
RAIL_ANIM = [("move", True), ("bone", True), "|", ("softbox", True), ("camera", True), ("sim", True)]
RAIL_RENDER = [("move", True), "|", ("softbox", True), ("camera", True)]


def rail(L, tools=RAIL_BUILD, active="move", opened=None, swap=None):
    out = []
    for t in tools:
        if t == "|":
            out.append('<div class="sep"></div>'); continue
        n, grp = t
        cls = " on" if n == active else " open" if n == opened else ""
        ic = (swap or {}).get(n, n)
        out.append(f'<div class="tool{cls}">{icon(ic, 18)}{"<span class=more></span>" if grp else ""}</div>')
    return f'<div class="abs rail" style="left:0;top:{HEAD}px;width:{RAIL}px;height:{L["ch"]}px">{"".join(out)}</div>'


def tool_y(tools, name):
    y = HEAD + 8
    for t in tools:
        if t == "|":
            y += 11; continue
        if t[0] == name:
            return y
        y += 38
    return y


# ---------------- settings panel pieces ----------------
def chev():
    return f'<span class="ch">{icon("chev",12,"#71747c")}</span>'


def row(label, field, dia=None, wide=False, h=None):
    d = '' if dia is None else f'<span class="dia{" on" if dia else ""}"></span>'
    st = f' style="height:{h}px"' if h else ""
    if wide:
        return f'<div class="r"{st}><div class="wide">{field}</div>{d}</div>'
    return f'<div class="r"{st}><span class="lb">{label}</span><div>{field}</div>{d}</div>'


def f(v, unit="", k="", extra="", cls=""):
    return (f'<div class="f {cls}">{f"<span class=k>{k}</span>" if k else ""}{v}'
            f'{f" <span class=u>{unit}</span>" if unit else ""}{extra}</div>')


def pair(a, b):
    return f'<div class="pair">{a}{b}</div>'


def trip(a, b, c):
    return f'<div class="trip">{a}{b}{c}</div>'


def xyz(x, y, z):
    return trip(f(x, k="X"), f(y, k="Y"), f(z, k="Z"))


def sec(title, first=False, plus=False):
    return f'<div class="sh{" first" if first else ""}"><span>{title}</span>{"<span class=plus>+</span>" if plus else ""}</div>'


def names(*ns):
    return f'<div class="names">{" · ".join(f"<span>{n}</span>" for n in ns)}</div>'


def ihead(ic, name, kind, back=False):
    b = f'<div class="ib" style="width:22px;height:22px;margin-left:-6px">{icon("back",14)}</div>' if back else icon(ic, 16, "#9a9ca4")
    return f'<div class="ihead">{b}<span class="nm">{name}</span><span class="knd">{kind}</span></div>'


def colour(hexv, extra=""):
    return f('<span class="sw" style="background:' + hexv + '"></span><span class="mono">' + hexv.upper() + '</span>', extra=extra)


def slider(v, frac):
    return (f'<div style="display:flex;align-items:center;gap:8px;width:100%"><div class="sl"><i style="width:{frac*100}%"></i>'
            f'<b style="left:{frac*100}%"></b></div><div class="f" style="width:46px;flex:none">{v}</div></div>')


def seg(opts, on):
    return '<div class="seg">' + "".join(f'<span class="{"on" if o == on else ""}">{o}</span>' for o in opts) + '</div>'


def mat(name, c):
    return f(f'<span class="ball" style="background:{c}"></span>{name}', extra=chev())


BALL = {"black": "radial-gradient(circle at 35% 30%,#6b6e75,#0b0b0c 55%)",
        "alu": "radial-gradient(circle at 35% 30%,#f4f5f7,#8e9299 60%,#4b4e54)",
        "gold": "radial-gradient(circle at 35% 30%,#ffe2bd,#d39a63 55%,#6e4523)",
        "copper": "radial-gradient(circle at 35% 30%,#f2b48c,#a2502a 55%,#4a2010)",
        "red": "radial-gradient(circle at 35% 30%,#ff8a8a,#a3001b 55%,#3d0009)",
        "navy": "radial-gradient(circle at 35% 30%,#5a76b5,#1d3466 60%,#0b1530)",
        "glass": "radial-gradient(circle at 35% 30%,#ffffff,#9fb2c4 40%,#33404d)",
        "rubber": "radial-gradient(circle at 35% 30%,#55575c,#1e1f22 60%)",
        "plastic": "radial-gradient(circle at 35% 30%,#ffffff,#d9d6d0 55%,#8a877f)"}


# ---------------- viewport overlays (fractions of the frame) ----------------
def svg(L, body):
    return f'<svg class="abs" style="left:0;top:0;overflow:visible" width="{L["fw"]:.0f}" height="{L["fh"]:.0f}">{body}</svg>'


def arrow(x, y, dx, dy, c):
    l = math.hypot(dx, dy); ux, uy = dx / l, dy / l
    ex, ey = x + dx, y + dy
    hx, hy = ex - ux * 11, ey - uy * 11
    px, py = -uy * 5, ux * 5
    return (f'<line x1="{x}" y1="{y}" x2="{hx}" y2="{hy}" stroke="{c}" stroke-width="2.4"/>'
            f'<path d="M{ex} {ey}L{hx+px} {hy+py}L{hx-px} {hy-py}z" fill="{c}"/>')


def gizmo_move(L, u, v):
    x, y = u * L["fw"], v * L["fh"]
    s = (f'<path d="M{x+12} {y-2}h14v-14h-14z" fill="{BZ}" fill-opacity=".35" stroke="{BZ}" stroke-opacity=".8"/>')
    s += arrow(x, y, 78, 14, RX) + arrow(x, y, 0, -82, GY) + arrow(x, y, -52, 44, BZ)
    s += f'<circle cx="{x}" cy="{y}" r="5" fill="#fff" stroke="#111" stroke-width="1"/>'
    return s


def gizmo_rotate(L, u, v, r=70):
    x, y = u * L["fw"], v * L["fh"]
    return (f'<circle cx="{x}" cy="{y}" r="{r+10}" fill="none" stroke="#ffffff" stroke-opacity=".35" stroke-width="1.2"/>'
            f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r*.32}" fill="none" stroke="{BZ}" stroke-width="2.4"/>'
            f'<ellipse cx="{x}" cy="{y}" rx="{r*.3}" ry="{r}" fill="none" stroke="{GY}" stroke-width="2.4"/>'
            f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r}" fill="none" stroke="{RX}" stroke-width="3.2" />'
            f'<circle cx="{x}" cy="{y}" r="4" fill="#fff"/>')


def outline_ellipse(L, u, v, ru, rv, rot=0):
    x, y, rx, ry = u * L["fw"], v * L["fh"], ru * L["fw"], rv * L["fh"]
    return (f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" transform="rotate({rot} {x} {y})" fill="none" stroke="{ACC}" '
            f'stroke-width="2" style="filter:drop-shadow(0 0 2px rgba(77,141,255,.8))"/>')


def outline_path(L, pts, close=True):
    d = "M" + " L".join(f"{u*L['fw']:.1f} {v*L['fh']:.1f}" for u, v in pts) + (" Z" if close else "")
    return f'<path d="{d}" fill="none" stroke="{ACC}" stroke-width="2" stroke-linejoin="round" style="filter:drop-shadow(0 0 2px rgba(77,141,255,.8))"/>'


def rounded_box(L, u0, v0, u1, v1, r=0.02):
    x, y, w, h = u0 * L["fw"], v0 * L["fh"], (u1 - u0) * L["fw"], (v1 - v0) * L["fh"]
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r*L["fw"]}" fill="none" stroke="{ACC}" stroke-width="2" '
            f'style="filter:drop-shadow(0 0 2px rgba(77,141,255,.8))"/>')


# ---------------- timeline ----------------
EG = {"out": "M1 9C1 4 5 1 11 1", "in": "M1 9C7 9 11 6 11 1", "smooth": "M1 9C6 9 6 1 11 1", "linear": "M1 9L11 1"}


def track(L, secs):
    lw = L["W"] - L["lcol"] - 22
    return lambda t: 8 + t * lw / secs, lw / secs


def pack(anims):
    lines = []
    for prop, keys in sorted(anims, key=lambda a: a[1][0][0]):
        a, b = keys[0][0], keys[-1][0]
        for ln in lines:
            if all(b <= k[0][0] or a >= k[-1][0] for _, k in ln):
                ln.append((prop, keys)); break
        else:
            lines.append([(prop, keys)])
    return lines or [[]]


def lane(X, anims, sel, selsp, full, cache=None):
    s = ""
    ts = [t for _, ks in anims for t, _ in ks]
    if ts:
        s += f'<div class="bar" style="left:{X(min(ts))}px;width:{X(max(ts))-X(min(ts))}px"></div>'
    if cache:
        a, b, txt = cache
        s += f'<div class="cache" style="left:{X(a)}px;width:{X(b)-X(a)}px">{txt}</div>'
    for prop, keys in anims:
        for i in range(len(keys) - 1):
            a, e = keys[i]; b = keys[i + 1][0]
            on = selsp == (prop, i)
            if on:
                s += f'<div class="sp sel" style="left:{X(a)}px;width:{X(b)-X(a)}px"></div>'
            if full and e:
                s += f'<svg class="eg{" s" if on else ""}" style="left:{(X(a)+X(b))/2}px" width="12" height="10"><path d="{EG[e]}" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>'
        for i, (t, _) in enumerate(keys):
            on = selsp and selsp[0] == prop and i in (selsp[1], selsp[1] + 1)
            s += f'<div class="kd{" s" if on else ""}{"" if full else " sm"}" style="left:{X(t)}px"></div>'
    return f'<div class="lane{" sel" if sel else ""}">{s}</div>'


def wave(X, secs):
    w = int(X(secs) - X(0))
    return "".join(f'<div style="position:absolute;left:{8+i}px;top:{14-a:.1f}px;width:2px;height:{2*a:.1f}px;background:#3fae8a"></div>'
                   for i in range(0, w, 3) for a in [6 * abs(math.sin(i / 23)) * (0.55 + 0.45 * abs(math.sin(i / 160))) + 1])


def timeline(L, items, playhead, secs=5.0, full=False, selsp=None, markers=(("logo lands", 3.2),), music=True):
    """items: (indent, icon, name, selected, anims, twisty, tag, cache)."""
    X, pps = track(L, secs)
    y, h, w = HEAD + L["ch"], L["T"], L["W"]
    ticks = "".join(f'<div class="tk{"" if s % 2 == 0 else " mn"}" style="left:{X(s/2)}px">{f"{s/2:g}s" if s % 2 == 0 else ""}</div>'
                    for s in range(0, int(secs * 2) + 1))
    lrows, lanes = [], []
    for ind, ic, nm, sel, anims, tw, tag, cache in items:
        lines = pack(anims) if full else [anims]
        for li, ln in enumerate(lines):
            if li == 0:
                lrows.append(f'<div class="lr{" sel" if sel else ""}" style="padding-left:{8+ind*14}px"><span class="tw">{tw}</span>'
                             f'<span class="ic">{icon(ic,13)}</span><span>{nm}</span>{f"<span class=tag>{tag}</span>" if tag else ""}</div>')
            else:
                lrows.append(f'<div class="lr sub{" sel" if sel else ""}" style="padding-left:{8+ind*14+32}px">{" · ".join(p for p, _ in ln)}</div>')
            ss = selsp[1:] if selsp and selsp[0] == nm else None
            lanes.append(lane(X, ln, sel, ss, full, cache if li == 0 else None))
    body = (h - TL_HEAD) // ROW
    pinned = body - (1 if music else 0)
    n = len(lrows)
    sc = f'<div class="scroll" style="top:4px;height:{max(20,(h-TL_HEAD-ROW)*pinned/n-8):.0f}px"></div>' if n > pinned else ""
    mk = "".join(f'<div class="mk" style="left:{X(t)-2}px">◆ {nm}</div>' for nm, t in markers)
    mkl = "".join(f'<div class="mkl" style="left:{X(t)}px"></div>' for nm, t in markers)
    mus_l = mus_n = ""
    if music:
        top = ROW * pinned
        mus_l = (f'<div class="lr" style="position:absolute;left:0;top:{top}px;width:100%;padding-left:8px;border-top:1px solid #222328">'
                 f'<span class="tw"></span><span class="ic">{icon("sound",13)}</span><span>Score</span><span class="tag">from Sound</span></div>')
        mus_n = f'<div class="lane" style="position:absolute;left:0;right:0;top:{top}px;border-top:1px solid #222328;background:#121a17">{wave(X, secs)}</div>'
    return f"""<div class="abs tl" style="left:0;top:{y}px;width:{w}px;height:{h}px">
 <div class="th"><div class="tr"><div class="ib" style="color:#fff">{icon('play',13)}</div><span class="time">{playhead:.2f} s</span>
  <span class="dim">/ {secs:.2f} s</span><div style="flex:1"></div><div class="ib">{icon('loop',14)}</div><div class="ib">{icon('marker',14)}</div>
  <div class="ib" style="color:{ACC}">{icon('magnet',14)}</div></div>
  <div class="ruler">{ticks}{mk}</div></div>
 <div class="lay">{''.join(lrows[:pinned])}{mus_l}</div>
 <div class="lanes">{mkl}{''.join(lanes[:pinned])}{mus_n}{sc}</div>
 <div class="ph" style="left:{L['lcol']+X(playhead)}px"></div></div>"""


# ---------------- the Aurora scene list ----------------
def aurora(sel="Case", lid=None):
    return [
        (0, "group", "Aurora case", False, [], "▾", "", None),
        (1, "cube", "Case", sel == "Case", [], "", "Black gloss", None),
        (1, "torus", "Lid", sel == "Lid", [("Rotate", [(0.8, "out"), (1.6, "")])], "", "Black gloss", None),
        (1, "capsule", "Bud L", False, [("Position", [(1.4, "smooth"), (2.2, "")])], "", "White plastic", None),
        (1, "capsule", "Bud R", False, [("Position", [(1.5, "smooth"), (2.3, "")])], "", "White plastic", None),
        (0, "cylinder", "Plinth", False, [], "", "Matte grey", None),
        (0, "text3d", "Wordmark", False, [("Position", [(2.6, "out"), (3.2, "")]), ("Opacity", [(2.4, "linear"), (2.9, "")])], "", "Brushed alu", None),
        (0, "softbox", "Key softbox", sel == "Key softbox", [], "", "450 W", None),
        (0, "strip", "Rim strip", False, [], "", "120 W", None),
        (0, "sky", "Sky", False, [], "", "studio_small_09", None),
        (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None),
    ]


# ---------------- page assembly ----------------
def page(name, L, *, img, settings, bottom, over="", hdr=None, rail_html=None, extra="", pos="50% 50%"):
    fx, fy = RAIL + (L["cw"] - L["fw"]) / 2, HEAD + (L["ch"] - L["fh"]) / 2
    vp = (f'<div class="abs vp" style="left:{RAIL}px;top:{HEAD}px;width:{L["cw"]}px;height:{L["ch"]}px"></div>'
          f'<div class="abs frame" style="left:{fx:.1f}px;top:{fy:.1f}px;width:{L["fw"]:.1f}px;height:{L["fh"]:.1f}px">'
          f'<img src="assets/{img}" style="object-position:{pos}">'
          f'<div class="abs" style="left:0;top:0">{over}</div></div>')
    ins = f'<div class="abs insp" style="left:{L["W"]-L["insp"]}px;top:{HEAD}px;width:{L["insp"]}px;height:{L["ch"]}px">{settings}</div>'
    html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title><style>{css(L)}</style></head><body>'
            f'{hdr or header(L)}{rail_html or rail(L)}{vp}{ins}{bottom}{extra}</body></html>')
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    return name, L


# ================= the screens =================
def s01(L, name="01-workspace-build"):
    st = (ihead("cube", "Case", "Rounded box") + sec("Transform", first=True) +
          row("Position <span class=dim>cm</span>", xyz("0", "1.2", "−3.5"), False) +
          row("Rotation <span class=dim>°</span>", xyz("0", "18", "0"), False) +
          row("Scale", f("100", "%"), False) +
          sec("Material") +
          row("Material", mat("Black gloss", BALL["black"])) +
          row("Base colour", colour("#0e0e10"), False) +
          row("Roughness", slider("0.08", .08), False) +
          row("Metal", slider("0.00", 0), False) +
          names("Bevel", "Shadows", "Visibility", "Motion blur"))
    over = svg(L, outline_ellipse(L, .505, .565, .425, .355) + gizmo_move(L, .5, .52))
    return page(name, L, img="case.jpg", settings=st, over=over, bottom=timeline(L, aurora("Case"), 1.0))


SHAPES = [("cube", "Box", "B"), ("sphere", "Sphere", ""), ("cylinder", "Cylinder", ""), ("cone", "Cone", ""),
          ("torus", "Torus", ""), ("capsule", "Capsule", ""), ("plane", "Plane", ""), ("disc", "Disc", "")]


def s02(L):
    tiles = "".join(f'<div class="tile{" on" if i == 0 else ""}">{icon(ic,22)}<span>{nm}</span>{f"<span class=kk>{k}</span>" if k else ""}</div>'
                    for i, (ic, nm, k) in enumerate(SHAPES))
    fly = (f'<div class="abs fly" style="left:{RAIL+6}px;top:{tool_y(RAIL_BUILD,"cube")-4}px">'
           f'<div style="display:grid;grid-template-columns:repeat(4,64px);gap:6px">{tiles}</div></div>')
    st = (ihead("film", "Hero 01", "Shot · nothing selected") + sec("View", first=True) +
          row("Exposure <span class=dim>EV</span>", slider("+0.3", .56), False) +
          row("Contact shadows", '<div class="tg"></div>') +
          row("World light", f('<span class="sw" style="background:linear-gradient(180deg,#d8d4cc,#6d6a66)"></span>studio_small_09', extra=chev())) +
          row("Light strength", slider("1.0", .5), False) +
          sec("Shot") +
          row("Size", f("1920 × 1080", extra=chev())) +
          row("Frame rate", f("24 fps", extra=chev())) +
          row("Length", f("5.00", "s")) +
          row("Camera", f("Camera rig · 35 mm", extra=chev())) +
          names("Fog", "Depth of field", "Colour", "Motion blur"))
    items = [(0, "cube", "Plinth", False, [], "", "Clay", None),
             (0, "cylinder", "Glass", False, [], "", "Clear glass", None),
             (0, "sphere", "Ball", False, [], "", "Brushed alu", None),
             (0, "plane", "Floor", False, [], "", "Floor grey", None),
             (0, "softbox", "Key softbox", False, [], "", "450 W", None),
             (0, "strip", "Rim strip", False, [], "", "120 W", None),
             (0, "sky", "Sky", False, [], "", "studio_small_09", None),
             (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None)]
    return page("02-shapes-flyout", L, img="still-life-quick.jpg", settings=st, bottom=timeline(L, items, 0.5, markers=()),
                rail_html=rail(L, opened="cube", active=None), extra=fly)


def s03(L):
    st = (ihead("text3d", "Wordmark", "3D text") + sec("Text", first=True) +
          row("Text", f("Rostrum")) +
          row("Font", f("Inter Display", extra=chev())) +
          row("Weight", f("Semibold", extra=chev())) +
          row("Size", f("12.0", "cm"), False) +
          sec("Depth and bevel") +
          row("Depth", f("1.2", "cm"), False) +
          row("Bevel size", f("0.30", "cm", cls="act"), False) +
          f'<div class="r" style="height:22px"><span></span><span class="note">Largest that fits: 0.22 cm</span></div>' +
          row("Bevel shape", seg(["Round", "Flat", "Step"], "Round")) +
          sec("Faces") +
          row("Front", mat("Rose gold", BALL["gold"])) +
          row("Bevel", mat("Polished gold", BALL["gold"])) +
          row("Side", mat("Rose gold", BALL["gold"])) +
          names("Transform", "Shadows", "Visibility", "Motion blur"))
    over = svg(L, rounded_box(L, .372, .405, .862, .615, .004) + gizmo_move(L, .62, .52))
    items = [(0, "logo", "Logo ring", False, [], "", "Rose gold", None),
             (0, "text3d", "Wordmark", True, [("Position", [(2.6, "out"), (3.2, "")])], "", "Rose gold", None),
             (0, "plane", "Backdrop", False, [], "", "Charcoal", None),
             (0, "softbox", "Key softbox", False, [], "", "450 W", None),
             (0, "strip", "Rim strip", False, [], "", "120 W", None),
             (0, "sky", "Sky", False, [], "", "studio_small_09", None),
             (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None)]
    return page("03-logo-extrude", L, img="wordmark.jpg", settings=st, over=over, bottom=timeline(L, items, 3.2),
                hdr=header(L, shot="Close 02"), rail_html=rail(L, active="text3d", swap={"text3d": "text3d"}))


PRESETS = [("Brushed alu", "alu"), ("Polished gold", "gold"), ("Black gloss", "black"), ("Copper", "copper"),
           ("Clear glass", "glass"), ("Rubber", "rubber")]


def picker(x, y):
    return f"""<div class="abs pop" style="left:{x}px;top:{y}px;width:256px;padding:10px">
 <div style="display:flex;gap:2px;margin-bottom:10px"><div class="ib" style="background:#34363d;color:#fff">{icon('solid',16)}</div>
  <div class="ib">{icon('image',16)}</div><div style="flex:1"></div><span class="dim" style="align-self:center">Base colour</span></div>
 <div style="position:relative;height:150px;border-radius:6px;background:linear-gradient(to top,#000,transparent),linear-gradient(to right,#fff,hsl(215,30%,50%))">
  <div style="position:absolute;left:{236*0.04-7}px;top:{150*0.18-7}px;width:14px;height:14px;border-radius:7px;border:2px solid #fff;box-shadow:0 0 2px #000"></div></div>
 <div style="position:relative;height:12px;border-radius:6px;margin-top:10px;background:linear-gradient(90deg,red,#ff0,lime,cyan,blue,#f0f,red)">
  <div style="position:absolute;left:{236*215/360-7}px;top:-1px;width:14px;height:14px;border-radius:7px;border:2px solid #fff;box-shadow:0 0 2px #000"></div></div>
 <div style="display:flex;gap:4px;margin-top:10px"><div class="ib" style="background:#212227">{icon('drop',15)}</div>
  <div class="f mono" style="flex:1">#C9CCD1</div><div class="f" style="width:64px;flex:none"><span class="k">sRGB</span></div></div>
 <div class="fh">Project</div>
 <div style="display:flex;gap:5px">{''.join(f'<span class="sw" style="width:20px;height:20px;background:{c}"></span>' for c in ['#0e0e10','#c9ccd1','#d39a63','#f4f1ea','#1d3466','#a3001b'])}<span style="color:#8d9099;font-size:15px;line-height:18px;margin-left:2px">+</span></div>
</div>"""


SHORT = ["Brushed", "Gold", "Black", "Copper", "Glass", "Rubber"]


def s04(L):
    strip = "".join(f'<div style="display:flex;flex-direction:column;align-items:center;gap:3px;width:42px;font-size:9.5px;color:{"#fff" if i == 0 else "#9a9ca4"};white-space:nowrap">'
                    f'<span class="ball" style="width:30px;height:30px;border-radius:15px;background:{BALL[b]};{"box-shadow:0 0 0 2px " + ACC if i == 0 else ""}"></span>{SHORT[i]}</div>'
                    for i, (n, b) in enumerate(PRESETS))
    st = (ihead("", "Brushed alu", "Material · on Disc", back=True) +
          f'<div style="display:flex;gap:4px;padding:10px {PAD_L}px 8px;border-bottom:1px solid #25262b">{strip}</div>' +
          sec("Surface", first=True) +
          row("Base colour", colour("#c9ccd1", extra=""), False).replace('class="f "', 'class="f act"') +
          row("Metal", slider("1.00", 1), False) +
          row("Roughness", slider("0.28", .28), False) +
          sec("Brushed") +
          row("Direction", seg(["Radial", "Straight", "Circular"], "Radial")) +
          row("Amount", slider("0.60", .6), False) +
          sec("Coat") +
          row("Coat", slider("0.15", .15), False) +
          row("Coat roughness", slider("0.05", .05), False) +
          names("Glass", "Glow", "Bumps", "Picture"))
    over = svg(L, outline_ellipse(L, .133, .468, .072, .148, 24))
    items = [(0, "disc", "Disc", True, [], "", "Brushed alu", None),
             (0, "cube", "Red cube", False, [], "", "Red gloss", None),
             (0, "torus", "Ring", False, [], "", "Navy matte", None),
             (0, "cube", "Glass block", False, [], "", "Frosted glass", None),
             (0, "card", "Screen card", False, [], "", "2D: Spring launch", None),
             (0, "plane", "Floor", False, [], "", "Black mirror", None),
             (0, "softbox", "Key softbox", False, [], "", "450 W", None),
             (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None)]
    px = L["W"] - L["insp"] - 268
    return page("04-material-picker", L, img="materials.jpg", settings=st, over=over, bottom=timeline(L, items, 0.0, markers=()),
                hdr=header(L, shot="Materials test"), extra=picker(px, HEAD + 92))


def s05(L):
    st = (ihead("softbox", "Key softbox", "Softbox light") + sec("Light", first=True) +
          row("Size <span class=dim>cm</span>", pair(f("120", k="W"), f("80", k="H")), False) +
          row("Power", f("450", "W"), False) +
          row("Colour", seg(["Colour", "Temperature"], "Temperature")) +
          row("Temperature", f('<span class="sw" style="background:#ffe9d2"></span>5600 <span class=u>K</span>'), False) +
          row("Spread", f("60", "°"), False) +
          sec("Lights only") +
          f'<div class="r" style="height:auto;padding:4px 0 6px {PAD_L}px"><div class="wide" style="display:flex;flex-wrap:wrap;gap:5px">'
          f'<span class="lchip">Plinth <span class="dim">×</span></span><span class="lchip">Glass <span class="dim">×</span></span>'
          f'<span class="lchip off">+ Add</span></div></div>' +
          f'<div class="r" style="margin-top:6px"><div class="wide" style="display:flex;gap:4px"><div class="bt">{icon("camera",13)} Look through light</div></div></div>' +
          names("Transform", "Shadows", "Visibility"))
    # the softbox: a lit card in the top-left, aimed at the glass (a light is drawn as its shape + aim line)
    fw, fh = L["fw"], L["fh"]
    q = [(.06, .10), (.22, .06), (.25, .30), (.09, .36)]
    pts = " ".join(f"{u*fw:.1f},{v*fh:.1f}" for u, v in q)
    lt = (f'<polygon points="{pts}" fill="rgba(255,240,220,.22)" stroke="{ACC}" stroke-width="2" style="filter:drop-shadow(0 0 2px rgba(77,141,255,.8))"/>'
          f'<line x1="{.155*fw}" y1="{.205*fh}" x2="{.47*fw}" y2="{.33*fh}" stroke="#ffe9a8" stroke-width="1.4" stroke-dasharray="5 4"/>'
          f'<circle cx="{.47*fw}" cy="{.33*fh}" r="4" fill="none" stroke="#ffe9a8" stroke-width="1.4"/>')
    over = svg(L, lt + gizmo_move(L, .155, .205))
    items = [(0, "cube", "Plinth", False, [], "", "Clay", None),
             (0, "cylinder", "Glass", False, [], "", "Clear glass", None),
             (0, "sphere", "Ball", False, [], "", "Brushed alu", None),
             (0, "plane", "Floor", False, [], "", "Floor grey", None),
             (0, "softbox", "Key softbox", True, [], "", "450 W", None),
             (0, "strip", "Rim strip", False, [], "", "120 W", None),
             (0, "sky", "Sky", False, [], "", "studio_small_09", None),
             (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None)]
    return page("05-lighting", L, img="still-life-final.jpg", settings=st, over=over, bottom=timeline(L, items, 1.0, markers=()),
                hdr=header(L, look="Final"), rail_html=rail(L, active="softbox"))


BRUSHES = [("Paint", [("Round hard", "#e9e3d6", 7, 0), ("Airbrush", "#cfcac2", 10, 4), ("Bristle", "#d8d2c4", 6, 1)]),
           ("Wear", [("Edge wear", "#a9aeb6", 4, 2), ("Scratches", "#b9bec6", 1.4, 3), ("Dust", "#8d8a84", 8, 5)]),
           ("Print", [("Decal", "#f2f2f2", 7, 0), ("Stencil", "#f2b84b", 7, 0)])]


def stroke(c, w, kind):
    if kind == 3:
        return "".join(f'<path d="M{6+i*7} {20-i%3*2}l{14} {-10+i%2*4}" stroke="{c}" stroke-width="1" opacity=".8"/>' for i in range(11))
    if kind == 5:
        return "".join(f'<circle cx="{8+(i*37)%84}" cy="{6+(i*13)%16}" r="{.6+(i%3)*.5}" fill="{c}"/>' for i in range(34))
    dash = ' stroke-dasharray="3 2 1 3"' if kind == 2 else ""
    blur = ' style="filter:blur(2.5px)"' if kind == 4 else ""
    op = ' opacity=".75"' if kind == 1 else ""
    return f'<path d="M6 18C30 6 60 22 90 10" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round"{dash}{blur}{op}/>'


def s06(L):
    tools = [("brush", "Brush", True), ("eraser", "Eraser", False), ("fill", "Fill", False), ("picker", "Pick", False)]
    top = "".join(f'<div class="tile{" on" if on else ""}" style="width:60px;height:52px">{icon(i,18)}<span>{n}</span></div>' for i, n, on in tools)
    body = ""
    for grp, bs in BRUSHES:
        body += f'<div class="fh">{grp}</div><div style="display:flex;gap:6px">'
        for n, c, w, k in bs:
            body += (f'<div class="bru{" on" if n == "Edge wear" else ""}"><svg width="96" height="26" style="background:#16171a;border-radius:4px">{stroke(c, w, k)}</svg>'
                     f'<span>{n}</span></div>')
        body += '</div>'
    fly = (f'<div class="abs fly" style="left:{RAIL+6}px;top:{tool_y(RAIL_BUILD,"brush")-6}px;width:340px">'
           f'<div style="display:flex;gap:4px;border-bottom:1px solid #2a2b30;padding-bottom:8px">{top}</div>{body}</div>')
    st = (ihead("brush", "Painting", "on Case") + sec("Brush", first=True) +
          row("Brush", f("Edge wear", extra=chev())) +
          row("Size", slider("18 px", .3)) +
          row("Strength", slider("60 %", .6)) +
          row("Paints", seg(["Colour", "Roughness", "Metal"], "Roughness")) +
          row("Colour", colour("#8a8f98")) +
          sec("Paint layers", plus=True) +
          ''.join(f'<div class="lr{" sel" if s else ""}" style="padding-left:{PAD_L}px;gap:8px">{icon("eye",13,"#8d9099")}<span>{n}</span>'
                  f'<span class="tag">{t}</span></div>' for n, t, s in
                  [("Scuffs", "Roughness", True), ("Logo print", "Colour", False), ("Base", "Black gloss", False)]) +
          sec("Seen by Hero 01") +
          f'<div class="r"><span class="wide" style="color:#d4d5da">camera sees 64 % · painted 41 %</span></div>' +
          names("Mask", "Symmetry", "Pressure"))
    fw, fh = L["fw"], L["fh"]
    cx, cy = .66 * fw, .44 * fh
    cur = (f'<circle cx="{cx}" cy="{cy}" r="34" fill="none" stroke="#fff" stroke-width="1.4"/>'
           f'<circle cx="{cx}" cy="{cy}" r="34" fill="none" stroke="#000" stroke-opacity=".5" stroke-width="1" transform="translate(1 1)"/>'
           f'<circle cx="{cx}" cy="{cy}" r="20" fill="none" stroke="#fff" stroke-opacity=".55" stroke-dasharray="3 3"/>'
           f'<circle cx="{cx}" cy="{cy}" r="1.8" fill="#fff"/>')
    over = svg(L, outline_ellipse(L, .505, .565, .425, .355) + cur)
    return page("06-paint-on-model", L, img="case.jpg", settings=st, over=over, bottom=timeline(L, aurora("Case"), 1.0),
                rail_html=rail(L, active="brush", opened=None), extra=fly)


EASES = [("Linear", "M2 14L24 2"), ("Smooth", "M2 14C12 14 14 2 24 2"), ("In", "M2 14C16 14 24 8 24 2"),
         ("Out", "M2 14C2 8 10 2 24 2"), ("Spring", "M2 14C6 -4 10 6 14 1S20 3 24 2"),
         ("Bounce", "M2 14Q8 0 12 2Q16 8 18 2Q21 5 24 2"), ("Hold", "M2 14H24V2")]


def curve_svg(w, h=104):
    pad = 10
    gw, gh = w - 2 * pad, h - 2 * pad - 10
    X = lambda v: pad + v * gw
    Y = lambda v: pad + 4 + (1 - v) * gh
    x1, y1, x2, y2 = .22, 1.0, .36, 1.0
    g = "".join(f'<line x1="{X(i/4)}" y1="{Y(0)}" x2="{X(i/4)}" y2="{Y(1)}" stroke="#25262b"/>' for i in range(5))
    g += "".join(f'<line x1="{X(0)}" y1="{Y(i/4)}" x2="{X(1)}" y2="{Y(i/4)}" stroke="#25262b"/>' for i in range(5))
    return f"""<svg width="{w}" height="{h}" style="display:block;background:#121316;border-radius:5px;border:1px solid #2d2e34">{g}
 <line x1="{X(0)}" y1="{Y(0)}" x2="{X(x1)}" y2="{Y(y1)}" stroke="#8d9099"/><line x1="{X(1)}" y1="{Y(1)}" x2="{X(x2)}" y2="{Y(y2)}" stroke="#8d9099"/>
 <path d="M{X(0)} {Y(0)} C{X(x1)} {Y(y1)} {X(x2)} {Y(y2)} {X(1)} {Y(1)}" fill="none" stroke="{ACC}" stroke-width="2.2"/>
 <circle cx="{X(x1)}" cy="{Y(y1)}" r="5" fill="#fff"/><circle cx="{X(x2)}" cy="{Y(y2)}" r="5" fill="#fff"/>
 <text x="{X(0)}" y="{h-3}" fill="#6f727a" font-size="10">0.80 s</text><text x="{X(1)-30}" y="{h-3}" fill="#6f727a" font-size="10">1.60 s</text></svg>"""


ROWS7 = ("Camera rig", "Lid", "Bud L", "Bud R", "Wordmark")


def s07(L):
    F, LC = grid(L["insp"])
    ez = lambda l, d: (f'<div class="ab{" on" if l == "Out" else ""}"><svg width="26" height="16" viewBox="0 0 26 16">'
                       f'<path d="{d}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><span>{l}</span></div>')
    st = (ihead("", "Rotate", "Lid · opens", back=True) + sec("From → to", first=True) +
          row("Turn X <span class=dim>°</span>", pair(f("0"), f("&nbsp;−105", k="→"))) +
          sec("Time") + row("Start", f("0.80", "s")) + row("Length", f("0.80", "s")) +
          sec("Easing") +
          f'<div class="r" style="height:44px"><div class="wide"><div class="ez">{"".join(ez(l, d) for l, d in EASES[:4])}</div></div></div>' +
          f'<div class="r" style="height:44px"><div class="wide"><div class="ez">{"".join(ez(l, d) for l, d in EASES[4:])}</div></div></div>' +
          f'<div class="r" style="height:110px"><div class="wide">{curve_svg(LC + F)}</div></div>' +
          f'<div class="r"><span></span><div style="display:flex;gap:4px"><div class="bt">{icon("reverse",13)} Reverse</div>'
          f'<div class="bt">{icon("trash",13)} Delete</div></div></div>')
    over = svg(L, outline_ellipse(L, .505, .37, .27, .135) + gizmo_rotate(L, .505, .37, 64))
    return page("07-animate-timeline", L, img="case.jpg", settings=st, over=over,
                bottom=timeline(L, sorted([i for i in aurora("Lid") if i[2] in ROWS7], key=lambda i: ROWS7.index(i[2])),
                                1.2, full=True, selsp=("Lid", "Rotate", 0)),
                hdr=header(L, page="Animate"), rail_html=rail(L, RAIL_ANIM))


def s08(L):
    passes = [("Beauty", True), ("Depth", True), ("Object IDs", True), ("Shadow catcher", True), ("Normals", False), ("Light groups", False)]
    st = (ihead("film", "Render", "Hero 01") + sec("What", first=True) +
          row("", seg(["This frame", "Hero 01", "All shots"], "Hero 01"), wide=True) +
          sec("Quality") +
          row("", seg(["Draft", "Good", "Final"], "Final"), wide=True) +
          row("More", f('<span class="dim">256 samples · noise cleaned</span>', extra=f'<span class="ch">{icon("chevr",12,"#71747c")}</span>')) +
          sec("Output") +
          row("Size", f("1920 × 1080 · 120 frames", extra=chev())) +
          row("Folder", f(f'{icon("folder",13,"#8d9099")}renders\\Hero 01\\v004')) +
          sec("Layers for the Editor") +
          f'<div class="r" style="height:auto;padding:2px 0 4px {PAD_L}px"><div class="wide" style="display:flex;flex-wrap:wrap;gap:5px">' +
          "".join(f'<span class="lchip{"" if on else " off"}">{icon("check",11) if on else "+"} {n}</span>' for n, on in passes) +
          '</div></div>' +
          f'<div class="est"><b>about 6 min</b> · 3 s a frame on this laptop<br><span class="dim">from a quarter-size test frame on the RTX 3050 · EXR layers, live link on</span></div>' +
          f'<div style="padding:10px {PAD_L}px 0 {PAD_L}px;display:flex;gap:6px"><div class="bt pri" style="height:32px">Render 120 frames</div></div>')
    # bottom: shots list (left) and render queue (right)
    shots = [("Hero 01", "5.0 s · 24 fps", "still-life-final.jpg", True), ("Close 02", "3.0 s · 24 fps", "wordmark.jpg", False),
             ("Drop 03", "4.0 s · 24 fps", "still-life-quick.jpg", False)]
    sl = "".join(f'<div class="lr{" sel" if s else ""}" style="height:44px;padding-left:10px;gap:9px"><img class="thumb" src="assets/{im}">'
                 f'<div><div>{n}</div><div class="dim" style="font-size:11px">{d}</div></div></div>' for n, d, im, s in shots)
    q = [("Hero 01 · Final", "frames 1–120", .28, "34 of 120 · about 4 min left", "Pause"),
         ("Close 02 · Good", "frames 1–72", 0, "waiting · about 1 min", "Remove"),
         ("Hero 01 · Draft", "frames 1–120", 1, "done 10:42 · placed in the Editor (live link)", "Send to 2D")]
    ql = "".join(f'<div class="qrow"><span style="width:150px;color:#fff">{n}</span><span class="dim" style="width:90px">{fr}</span>'
                 f'<div class="prog"><i style="width:{p*100}%;{"background:#3fae8a" if p == 1 else ""}"></i></div>'
                 f'<span class="dim" style="flex:1">{t}</span><div class="bt" style="flex:none;padding:0 12px">{a}</div></div>' for n, fr, p, t, a in q)
    y, h = HEAD + L["ch"], L["T"]
    bottom = (f'<div class="abs tl" style="left:0;top:{y}px;width:{L["W"]}px;height:{h}px">'
              f'<div class="th"><div class="tr"><b style="color:#fff">Shots</b><div style="flex:1"></div><span class="dim">3</span></div>'
              f'<div class="ruler" style="display:flex;align-items:center;padding-left:12px;color:#fff;font-size:12px;font-weight:600">Render queue'
              '</div></div>'
              f'<div class="lay">{sl}</div><div class="lanes">{ql}</div></div>')
    return page("08-render-sheet", L, img="still-life-final.jpg", settings=st, bottom=bottom,
                hdr=header(L, page="Render", look="Final", status="Rendering Hero 01 · 34 / 120"), rail_html=rail(L, RAIL_RENDER, active="move"))


def s09(L):
    acts = [("union", "Union"), ("subtract", "Subtract"), ("intersect", "Intersect")]
    al = "".join(f'<div class="ib" style="width:30px;background:#232428;border:1px solid #2d2e34">{icon(a,15)}</div>' for a in ["al", "ac", "ar", "at", "am", "ab"])
    st = (ihead("cube", "2 solids", "Rounded box, Torus") + sec("Combine", first=True) +
          f'<div class="r" style="height:46px"><div class="wide" style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px">' +
          "".join(f'<div class="ab">{icon(i,16)}<span>{n}</span></div>' for i, n in acts) + '</div></div>' +
          f'<div class="r"><div class="wide" style="display:flex;gap:4px"><div class="bt">{icon("group",13)} Group</div><div class="bt">Copy material</div></div></div>' +
          sec("Align") + f'<div class="r"><div class="wide" style="display:flex;gap:4px">{al}</div></div>' +
          sec("Transform") +
          row("Position <span class=dim>cm</span>", trip(f('<span class="mx">Mixed</span>', k="X"), f("0", k="Y"), f('<span class="mx">Mixed</span>', k="Z")), False) +
          row("Rotation <span class=dim>°</span>", trip(f("0", k="X"), f('<span class="mx">Mixed</span>', k="Y"), f("0", k="Z")), False) +
          row("Scale", f("100", "%"), False) +
          sec("Material") +
          row("Material", f('<span class="mx">Mixed</span> <span class="dim">· 2 materials</span>', extra=chev())) +
          names("Bevel", "Shadows", "Visibility"))
    over = svg(L, outline_path(L, [(.247, .47), (.29, .43), (.385, .43), (.392, .48), (.39, .62), (.36, .655), (.27, .655), (.247, .62)])
               + outline_ellipse(L, .5, .47, .066, .145, 22) + gizmo_move(L, .41, .56))
    items = [(0, "disc", "Disc", False, [], "", "Brushed alu", None),
             (0, "cube", "Red cube", True, [], "", "Red gloss", None),
             (0, "torus", "Ring", True, [], "", "Navy matte", None),
             (0, "cube", "Glass block", False, [], "", "Frosted glass", None),
             (0, "card", "Screen card", False, [], "", "2D: Spring launch", None),
             (0, "plane", "Floor", False, [], "", "Black mirror", None),
             (0, "softbox", "Key softbox", False, [], "", "450 W", None),
             (0, "orbit", "Camera rig", False, [("Orbit", [(0.0, "linear"), (5.0, "")])], "", "Orbit", None)]
    return page("09-boolean-two-solids", L, img="materials.jpg", settings=st, over=over, bottom=timeline(L, items, 0.0, markers=()),
                hdr=header(L, shot="Materials test"))


def s10(L):
    st = (ihead("capsule", "12 buds", "Rigid bodies") + sec("Simulation", first=True) +
          row("Kind", f("Rigid body", extra=chev())) +
          row("Mass", f("4.5", "g")) +
          row("Bounce", slider("0.30", .3)) +
          row("Friction", slider("0.60", .6)) +
          row("Collision shape", f("Close fit", extra=chev())) +
          row("Start at", f("0.0", "s")) +
          f'<div class="r" style="margin-top:6px"><div class="wide" style="display:flex;gap:4px"><div class="bt pri">{icon("sim",13,"#fff")} Simulate</div>'
          f'<div class="bt">Clear</div></div></div>' +
          f'<div class="r"><span class="lb">Stored</span><span style="white-space:nowrap;color:#bfe9da">0.0–3.0 s · 72 frames</span></div>' +
          f'<div class="r"><span class="lb">Seen by shot</span><span style="white-space:nowrap">12 of 12 buds in view</span></div>' +
          sec("Collides with") +
          f'<div class="r" style="height:auto;padding:2px 0 4px {PAD_L}px"><div class="wide" style="display:flex;flex-wrap:wrap;gap:5px">'
          f'<span class="lchip">Glass <span class="dim">×</span></span><span class="lchip">Plinth <span class="dim">×</span></span><span class="lchip off">+ Add</span></div></div>' +
          names("Transform", "Material", "Visibility"))
    # twelve buds at 1.0 s, mid-fall over the glass: drawn as selection outlines (no render of the buds exists yet)
    fw, fh = L["fw"], L["fh"]
    buds = ""
    spots = [(.40, .05, 30), (.44, .13, -20), (.48, .03, 70), (.52, .11, 10), (.47, .20, -50), (.42, .24, 40),
             (.53, .26, -15), (.50, .33, 60), (.44, .36, -35), (.475, .44, 20), (.51, .48, -60), (.455, .50, 80)]
    for u, v, r in spots:
        buds += (f'<rect x="{u*fw-7}" y="{v*fh-14}" width="14" height="28" rx="7" transform="rotate({r} {u*fw} {v*fh})" '
                 f'fill="rgba(240,240,240,.10)" stroke="{ACC}" stroke-width="1.8" style="filter:drop-shadow(0 0 2px rgba(77,141,255,.8))"/>')
    over = svg(L, buds)
    items = [(0, "group", "Buds × 12", True, [], "▸", "Rigid bodies", (0.0, 3.0, "Simulated 0.0–3.0 s · stored")),
             (0, "cylinder", "Glass", False, [], "", "Collider", None),
             (0, "cube", "Plinth", False, [], "", "Collider", None),
             (0, "sphere", "Ball", False, [], "", "Brushed alu", None),
             (0, "plane", "Floor", False, [], "", "Floor grey", None),
             (0, "softbox", "Key softbox", False, [], "", "450 W", None),
             (0, "orbit", "Camera rig", False, [("Push in", [(0.0, "smooth"), (4.0, "")])], "", "Dolly", None)]
    return page("10-simulate", L, img="still-life-final.jpg", settings=st, over=over,
                bottom=timeline(L, items, 1.0, secs=4.0, markers=(("buds land", 1.8),)),
                hdr=header(L, shot="Drop 03"), rail_html=rail(L, active="sim"))


def build():
    L = layout()
    jobs = [s01(L), s02(L), s03(L), s04(L), s05(L), s06(L), s07(L), s08(L), s09(L), s10(L)]
    for W, H in [(1280, 720), (1920, 1080)]:
        jobs.append(s01(layout(W, H), f"01-workspace-build-{W}x{H}"))
    return jobs


def shoot(name, L):
    """Screenshot one page with Edge headless; Edge gets its own profile folder and is ended by PID if it hangs."""
    prof = tempfile.mkdtemp(prefix="r3d-edge-")
    p = subprocess.Popen([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                          f"--window-size={L['W']},{L['H']}", f"--screenshot={OUT / (name + '.png')}", (OUT / f"{name}.html").as_uri()],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        raise SystemExit(f"Edge did not finish {name} in 60 s (ended PID {p.pid})")
    shutil.rmtree(prof, ignore_errors=True)
    if not (OUT / f"{name}.png").exists():
        raise SystemExit(f"no picture written for {name}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1:]
    for name, L in build():
        if not only or any(o in name for o in only):
            shoot(name, L)
            print("wrote", name + ".png")
