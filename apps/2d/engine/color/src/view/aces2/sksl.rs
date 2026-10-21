//! ACES 2.0 as SkSL (UNTESTED here: no Skia in this crate): a line-by-line transliteration of `mod.rs`,
//! `cam.rs`, `tonescale.rs` and `gamut.rs`, with every number taken from the built `Aces2` (no second copy).
//! Skia runtime effects are ES2-strict: uniform arrays may only be indexed by loop indices, so the per-hue
//! tables are read with full loops (~730 iterations per pixel). An image child would be faster. The tables are
//! `float4` arrays: a GL driver gives each element of a `float` array a whole vec4 slot, and 5 × 363 of those
//! overflowed the fragment uniform limit (the program failed to link and Skia drew nothing, silently).
use super::super::sksl::{f, mat};
use super::{Aces2, cam::Jmh, tables::N};

/// The uniforms the code declares, in order: `tab` (per hue: hue, cusp J, cusp M, 1 / top gamma) and `rch`
/// (per hue: reach M, 0, 0, 0), 363 `float4`s each.
pub(crate) fn uniforms(a: &Aces2) -> Vec<(&'static str, Vec<f32>)> {
    let tab = a.g.hues.iter().zip(&a.g.cusp).flat_map(|(h, c)| [*h, c[0], c[1], c[2]]).collect();
    let rch = a.reach.iter().flat_map(|r| [*r, 0.0, 0.0, 0.0]).collect();
    vec![("tab", tab), ("rch", rch)]
}

fn model(p: &Jmh, s: &str) -> String {
    format!(
        "const float3x3 RGB_CAM_{s} = {}; const float3x3 CAM_RGB_{s} = {};\n\
         const float3x3 CONE_AAB_{s} = {}; const float3x3 AAB_CONE_{s} = {};\n",
        mat(&p.rgb_cam), mat(&p.cam_rgb), mat(&p.cone_aab), mat(&p.aab_cone)
    )
}

const BODY: &str = r#"
float3 coneF(float3 v) { float3 p = pow(abs(v), float3(0.42)); return sign(v) * p / (NL + p); }
float3 coneI(float3 v) { float3 r = min(abs(v), float3(0.99)); return sign(v) * pow(NL * r / (1.0 - r), float3(1.0 / 0.42)); }
float coneF1(float v) { float p = pow(abs(v), 0.42); return p / (NL + p); }
float coneI1(float v) { float r = min(v, 0.99); return pow(NL * r / (1.0 - r), 1.0 / 0.42); }
float aToJ(float a) { return 100.0 * pow(a, CZ); }
float jToA(float j) { return pow(j * 0.01, 1.0 / CZ); }
float aToY(float a) { return coneI1(A_W_J * a) / F_L_N; }
float yToJ(float y) { return aToJ(coneF1(y * F_L_N) / A_W_J); }
float3 aabToJmh(float3 aab) {
    if (aab.x <= 0.0) { return float3(0.0); }
    float h = 180.0 * atan(aab.z, aab.y) / PI;
    return float3(aToJ(aab.x), length(aab.yz), h < 0.0 ? h + 360.0 : h);
}
float reachAt(float h) {
    float b = floor(h); float r = 0.0;
    for (int i = 0; i < 362; i++) { if (float(i) == b + 1.0) { r = mix(rch[i].x, rch[i + 1].x, h - b); } }
    return r;
}
float norm(float c1, float s1) {
    float c2 = 2.0 * c1 * c1 - 1.0; float s2 = 2.0 * c1 * s1;
    float c3 = 4.0 * c1 * c1 * c1 - 3.0 * c1; float s3 = 3.0 * s1 - 4.0 * s1 * s1 * s1;
    return (11.34072 * c1 + 16.46899 * c2 + 7.88380 * c3 + 14.66441 * s1 - 6.37224 * s2 + 9.19364 * s3 + 77.12896) * CC_SCALE;
}
float toe(float x, float limit, float k1i, float k2i, bool inv) {
    if (x > limit) { return x; }
    float k2 = max(k2i, 0.001); float k1 = sqrt(k1i * k1i + k2 * k2); float k3 = (limit + k1) / (limit + k2);
    if (inv) { return (x * x + k1 * x) / (k3 * (x + k2)); }
    float mb = k3 * x - k1; float mac = k2 * k3 * x;
    return 0.5 * (mb + sqrt(mb * mb + 4.0 * mac));
}
float tsFwdY(float y) { float f = M_2 * pow(y / (y + S_2), G); return max(0.0, f * f / (f + T_1)) * 100.0; }
float tsInvY(float y) {
    float z = max(0.0, min(INV_LIMIT, y / 100.0)); float f = (z + sqrt(z * (4.0 * T_1 + z))) / 2.0;
    return S_2 / (pow(M_2 / f, 1.0 / G) - 1.0);
}
float3 chroma(float3 jmh, float jOther, float mn, float rm, bool inv) {
    float jts = inv ? jmh.x : jOther; float j = inv ? jOther : jmh.x;
    if (jmh.y == 0.0) { return float3(jOther, jmh.y, jmh.z); }
    float nj = jts / LIMIT_J; float snj = max(0.0, 1.0 - nj);
    float limit = pow(nj, MG_INV) * rm / mn; float st = sqrt(nj * nj + SAT_THR);
    if (!inv) {
        float m = jmh.y * pow(jts / j, MG_INV) / mn;
        m = limit - toe(limit - m, limit - 0.001, snj * SAT, st, false);
        return float3(jts, toe(m, limit, nj * COMPR, snj, false) * mn, jmh.z);
    }
    float m = toe(jmh.y / mn, limit, nj * COMPR, snj, true);
    m = limit - toe(limit - m, limit - 0.001, snj * SAT, st, true);
    return float3(j, m * mn * pow(jts / j, -MG_INV), jmh.z);
}
float focusJ(float cj) { return mix(cj, MID_J, min(1.0, 1.3 - cj / LIMIT_J)); }
float gain(float j, float thr) {
    float g = LIMIT_J * FOCUS_DIST;
    if (j > thr) { float a = log((LIMIT_J - thr) / max(0.0001, LIMIT_J - j)) * 0.4342944819; g *= a * a + 1.0; }
    return g;
}
float jIntersect(float j, float m, float fj, float sg) {
    float ms = m / sg; float a = ms / fj;
    if (j < fj) { float b = 1.0 - ms; float c = -j; return -2.0 * c / (b + sqrt(b * b - 4.0 * a * c)); }
    float b = -(1.0 + ms + LIMIT_J * a); float c = LIMIT_J * ms + j;
    return -2.0 * c / (b - sqrt(b * b - 4.0 * a * c));
}
float slope(float ji, float fj, float sg) { return (ji < fj ? ji : LIMIT_J - ji) * (ji - fj) / (fj * sg); }
float lineM(float ja, float sl, float ig, float jm, float mm, float jr) {
    return jr * pow(ja / jr, ig) * mm / (jm - sl * mm);
}
float sminS(float a, float b, float r) {
    float s = 0.12 * r; float h = max(s - abs(a - b), 0.0) / s; return min(a, b) - h * h * h * s * (1.0 / 6.0);
}
float remap(float m, float gm, float rm, bool inv) {
    float pr = max(gm / rm, 0.75); float th = pr * gm;
    if (m <= th || pr >= 1.0) { return m; }
    float ro = rm - th; float sc = ro / (ro / (gm - th) - 1.0); float nd = (m - th) / sc;
    if (!inv) { return th + sc * nd / (1.0 + nd); }
    return th + (nd >= 1.0 ? sc : sc * -(nd / (nd - 1.0)));
}
// (cusp J, cusp M, 1 / top gamma) at hue h, as `Gamut::hull`.
float3 cuspAt(float h) {
    float3 c = float3(0.0);
    for (int i = 0; i < 362; i++) {
        if (h > tab[i].x && h <= tab[i + 1].x) {
            float t = (h - tab[i].x) / (tab[i + 1].x - tab[i].x);
            c = mix(tab[i].yzw, tab[i + 1].yzw, t);
        }
    }
    return c;
}
float3 compress(float3 jmh, float jx, float3 cu, float rm, bool inv) {
    float fj = focusJ(cu.x); float sg = gain(jx, mix(cu.x, LIMIT_J, 0.3));
    float js = jIntersect(jmh.x, jmh.y, fj, sg); float sl = slope(js, fj, sg);
    float jc = jIntersect(cu.x, cu.y, fj, sg);
    float lo = lineM(js, sl, LOWER_INV, cu.x, cu.y, jc);
    float up = lineM(LIMIT_J - js, -sl, cu.z, LIMIT_J - cu.x, cu.y, LIMIT_J - jc);
    float gm = sminS(lo, up, cu.y);
    if (gm <= 0.0) { return float3(jmh.x, 0.0, jmh.z); }
    float mr = remap(jmh.y, gm, lineM(js, sl, MG_INV, LIMIT_J, rm, LIMIT_J), inv);
    return float3(js + mr * sl, mr, jmh.z);
}
float3 gamut(float3 jmh, float rm, bool inv) {
    if (jmh.x <= 0.0) { return float3(0.0, 0.0, jmh.z); }
    if (jmh.y <= 0.0 || jmh.x > LIMIT_J) { return float3(jmh.x, 0.0, jmh.z); }
    float3 cu = cuspAt(jmh.z);
    float jx = jmh.x;
    if (inv && jx > mix(cu.x, LIMIT_J, 0.3)) { jx = compress(jmh, jx, cu, rm, true).x; }
    return compress(jmh, jx, cu, rm, inv);
}
float3 acesFwd(float3 cg) {
    float3 aab = CONE_AAB_IN * coneF(IN_M * clamp(cg, 0.0, FWD_LIMIT));
    float3 jmh = aabToJmh(aab);
    bool hue = aab.x > 0.0 && jmh.y > 0.0; float cs = hue ? aab.y / jmh.y : 1.0; float sn = hue ? aab.z / jmh.y : 0.0;
    float mn = norm(cs, sn); float rm = reachAt(jmh.z);
    float jts = aab.x > 0.0 ? yToJ(tsFwdY(aToY(aab.x))) : 0.0;
    float3 c = gamut(chroma(jmh, jts, mn, rm, false), rm, false);
    float3 rgb = CAM_RGB_OUT * coneI(AAB_CONE_OUT * float3(jToA(c.x), c.y * cs, c.y * sn));
    return LIM_DISP * clamp(rgb, 0.0, PEAK);
}
float3 acesInv(float3 d) {
    float3 rgb = clamp(DISP_LIM * d, 0.0, PEAK);
    float3 ca = CONE_AAB_OUT * coneF(RGB_CAM_OUT * rgb); float3 cj = aabToJmh(ca);
    bool hue = ca.x > 0.0 && cj.y > 0.0; float cs = hue ? ca.y / cj.y : 1.0; float sn = hue ? ca.z / cj.y : 0.0;
    float mn = norm(cs, sn); float rm = reachAt(cj.z);
    float3 tm = gamut(cj, rm, true);
    float j = tm.x > 0.0 ? yToJ(tsInvY(aToY(jToA(tm.x)))) : 0.0;
    float3 jmh = chroma(tm, j, mn, rm, true);
    float3 ap1 = OUT_M * coneI(AAB_CONE_IN * float3(jToA(jmh.x), jmh.y * cs, jmh.y * sn));
    return clamp(ap1, 0.0, FWD_LIMIT);
}
"#;

/// The ACES 2.0 functions `acesFwd` (ACEScg → display linear) and `acesInv`, with their constants.
pub(crate) fn code(a: &Aces2) -> String {
    let id = crate::view::IDENTITY;
    let (ld, dl) = a.lim_disp.as_ref().map_or((id, id), |m| *m);
    let p = &a.p_in;
    let consts = [
        ("PI", super::cam::PI), ("NL", 0.2713 * 100.0), ("CZ", p.cz), ("A_W_J", p.a_w_j), ("F_L_N", p.f_l_n),
        ("M_2", a.ts.m_2), ("S_2", a.ts.s_2), ("G", a.ts.g), ("T_1", a.ts.t_1), ("INV_LIMIT", a.ts.inverse_limit),
        ("FWD_LIMIT", a.ts.forward_limit), ("LIMIT_J", a.limit_j_max), ("MG_INV", a.model_gamma_inv),
        ("SAT", a.cc.sat), ("SAT_THR", a.cc.sat_thr), ("COMPR", a.cc.compr), ("CC_SCALE", a.cc.scale),
        ("MID_J", a.g.mid_j), ("FOCUS_DIST", a.g.focus_dist), ("LOWER_INV", a.g.lower_gamma_inv), ("PEAK", a.peak),
    ];
    let mut s: String = ["tab", "rch"].iter().map(|u| format!("uniform float4 {u}[{N}];\n")).collect();
    s += &consts.iter().map(|(k, v)| format!("const float {k} = {};\n", f(*v))).collect::<String>();
    s += &format!("const float3x3 IN_M = {}; const float3x3 OUT_M = {};\n", mat(&a.in_m), mat(&a.out_m));
    s += &format!("const float3x3 LIM_DISP = {}; const float3x3 DISP_LIM = {};\n", mat(&ld), mat(&dl));
    s + &model(&a.p_in, "IN") + &model(&a.p_out, "OUT") + BODY
}
