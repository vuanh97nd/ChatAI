"""Geotechnical calculation engine — runs in-process, no Docker required.

Supported formulas (pass as `formula` parameter):
  bearing_capacity   — Terzaghi/Meyerhof/Hansen bearing capacity of shallow footing
  settlement         — Terzaghi consolidation settlement
  earth_pressure     — Rankine active/passive earth pressure
  slope_stability    — Simplified Bishop / Fellenius factor of safety
  spt_correlation    — SPT N-value → friction angle, undrained shear strength, etc.
  mohr_coulomb       — Mohr-Coulomb failure envelope & principal stresses

Each formula receives a `params` JSON string and returns structured results with
formulas used, intermediate values, and final answers with units.
"""
import json
import math


# ──────────────────────────────────────────────────────────────────────────────
# Bearing-capacity factors (Terzaghi, also used by Meyerhof/Hansen)
# ──────────────────────────────────────────────────────────────────────────────

def _bc_factors_terzaghi(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ng) bearing-capacity factors for Terzaghi (1943)."""
    phi = math.radians(phi_deg)
    if phi == 0:
        Nq = 1.0
        Nc = 5.7
        Ng = 0.0
    else:
        Kphi = math.exp(math.pi * math.tan(phi))
        Nq = Kphi * math.tan(math.radians(45 + phi_deg / 2)) ** 2
        Nc = (Nq - 1) / math.tan(phi)
        Ng = (Nq - 1) * math.tan(1.4 * phi)
    return Nc, Nq, Ng


def _bc_factors_meyerhof(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ng) bearing-capacity factors for Meyerhof (1963)."""
    phi = math.radians(phi_deg)
    Nq = math.exp(math.pi * math.tan(phi)) * math.tan(math.radians(45 + phi_deg / 2)) ** 2
    Nc = (Nq - 1) / math.tan(phi) if phi > 0 else 5.14
    Ng = (Nq - 1) * math.tan(1.4 * phi)
    return Nc, Nq, Ng


# ──────────────────────────────────────────────────────────────────────────────
# Formula handlers
# ──────────────────────────────────────────────────────────────────────────────

def _bearing_capacity(p: dict) -> dict:
    """
    Required params: c (kPa), phi (°), gamma (kN/m³), B (m), Df (m)
    Optional: L (m, default=B for square), method ('Terzaghi'|'Meyerhof', default Meyerhof),
              shape ('strip'|'square'|'circular'|'rectangular', default 'square'),
              surcharge_q (kPa, extra surcharge beyond γ·Df)
    """
    c = float(p.get('c', 0))
    phi_deg = float(p['phi'])
    gamma = float(p['gamma'])
    B = float(p['B'])
    Df = float(p.get('Df', p.get('D', p.get('depth', 1.0))))
    L = float(p.get('L', B))
    method = p.get('method', 'Meyerhof')
    shape = p.get('shape', 'square' if abs(B - L) < 0.01 else 'rectangular')
    q = gamma * Df + float(p.get('surcharge_q', 0))

    if phi_deg < 0 or phi_deg >= 90:
        raise ValueError("phi phải trong khoảng [0, 90)°.")
    if c < 0 or gamma <= 0 or B <= 0 or Df < 0 or L <= 0:
        raise ValueError("Thông số không hợp lệ (c≥0, γ>0, B>0, Df≥0, L>0).")

    if method == 'Terzaghi':
        Nc, Nq, Ng = _bc_factors_terzaghi(phi_deg)
    else:
        method = 'Meyerhof'
        Nc, Nq, Ng = _bc_factors_meyerhof(phi_deg)

    # Shape factors (Meyerhof)
    if shape in ('square', 'circular'):
        sc, sq, sg = 1.3, 1.0, 0.8
    elif shape == 'strip':
        sc, sq, sg = 1.0, 1.0, 1.0
    else:  # rectangular
        ratio = B / L
        sc = 1 + 0.2 * ratio
        sq = 1 + 0.1 * ratio if phi_deg > 10 else 1.0
        sg = 1 - 0.1 * ratio if phi_deg > 10 else 1.0

    qu = c * Nc * sc + q * Nq * sq + 0.5 * gamma * B * Ng * sg
    qa = qu / 3.0

    return {
        "formula": f"qu = c·Nc·sc + q·Nq·sq + 0.5·γ·B·Nγ·sγ  ({method})",
        "factors": {"Nc": round(Nc, 3), "Nq": round(Nq, 3), f"Nγ": round(Ng, 3)},
        "shape_factors": {"sc": round(sc, 3), "sq": round(sq, 3), f"sγ": round(sg, 3)},
        "q_surcharge_kPa": round(q, 2),
        "qu_kPa": round(qu, 2),
        "qu_kN_m2": round(qu, 2),
        "qa_kPa (FS=3)": round(qa, 2),
        "method": method,
        "shape": shape,
    }


def _settlement(p: dict) -> dict:
    """
    Consolidation settlement (Terzaghi, 1D).
    Required: H (m), e0 (-), Cc (-), sigma0 (kPa, effective overburden),
              delta_sigma (kPa, stress increase)
    Optional: Cs (swelling index, default 0), sigma_p (preconsolidation pressure, kPa)
    """
    H = float(p['H'])
    e0 = float(p['e0'])
    Cc = float(p['Cc'])
    s0 = float(p['sigma0'])
    ds = float(p['delta_sigma'])
    Cs = float(p.get('Cs', 0))
    sp = float(p.get('sigma_p', s0))  # preconsolidation; default = normally consolidated

    if H <= 0 or e0 <= 0 or Cc <= 0 or s0 <= 0 or ds < 0:
        raise ValueError("Thông số không hợp lệ (H,e0,Cc,σ₀>0; Δσ≥0).")

    s1 = s0 + ds
    if sp <= s0:  # normally consolidated
        S = Cc / (1 + e0) * H * math.log10(s1 / s0)
        mode = "Normally consolidated (NC)"
    elif s1 <= sp:  # over-consolidated, stays OC
        S = Cs / (1 + e0) * H * math.log10(s1 / s0)
        mode = "Over-consolidated (OC), không vượt áp lực tiền cố kết"
    else:  # crosses preconsolidation
        S1 = Cs / (1 + e0) * H * math.log10(sp / s0)
        S2 = Cc / (1 + e0) * H * math.log10(s1 / sp)
        S = S1 + S2
        mode = "Over-consolidated → normally consolidated (vượt σ'p)"

    return {
        "formula": "S = Cc/(1+e₀) · H · log₁₀((σ₀'+Δσ)/σ₀')",
        "mode": mode,
        "S_m": round(S, 4),
        "S_cm": round(S * 100, 2),
        "S_mm": round(S * 1000, 1),
        "sigma0_kPa": s0,
        "delta_sigma_kPa": ds,
        "sigma1_kPa": round(s1, 2),
        "OCR": round(sp / s0, 2),
    }


def _earth_pressure(p: dict) -> dict:
    """
    Rankine active & passive earth pressure.
    Required: gamma (kN/m³), H (m), phi (°)
    Optional: c (kPa, default 0), delta_wall (°, default 0), surcharge (kPa, default 0)
    """
    gamma = float(p['gamma'])
    H = float(p['H'])
    phi_deg = float(p['phi'])
    c = float(p.get('c', 0))
    surcharge = float(p.get('surcharge', 0))

    if phi_deg < 0 or phi_deg >= 90 or H <= 0 or gamma <= 0:
        raise ValueError("Thông số không hợp lệ.")

    phi = math.radians(phi_deg)
    sin_phi = math.sin(phi)
    Ka = (1 - sin_phi) / (1 + sin_phi)
    Kp = (1 + sin_phi) / (1 - sin_phi)

    # Active pressure (Rankine)
    Pa_total = 0.5 * Ka * gamma * H ** 2 + Ka * surcharge * H - 2 * c * math.sqrt(Ka) * H
    Pa_at_base = Ka * (gamma * H + surcharge) - 2 * c * math.sqrt(Ka)
    Pp_total = 0.5 * Kp * gamma * H ** 2 + 2 * c * math.sqrt(Kp) * H
    Pp_at_base = Kp * gamma * H + 2 * c * math.sqrt(Kp)

    # Tension crack depth
    zc = 2 * c / (gamma * math.sqrt(Ka)) if gamma > 0 and Ka > 0 else 0

    return {
        "formula_Ka": "Ka = (1−sin φ)/(1+sin φ)",
        "formula_Kp": "Kp = (1+sin φ)/(1−sin φ)",
        "Ka": round(Ka, 4),
        "Kp": round(Kp, 4),
        "Pa_resultant_kN_per_m": round(max(Pa_total, 0), 2),
        "Pa_at_base_kPa": round(Pa_at_base, 2),
        "Pp_resultant_kN_per_m": round(Pp_total, 2),
        "Pp_at_base_kPa": round(Pp_at_base, 2),
        "tension_crack_depth_m": round(zc, 2) if c > 0 else 0,
        "note": "Rankine (tường thẳng đứng, đất lấp phẳng). Với tường nghiêng/đất nghiêng dùng Coulomb.",
    }


def _slope_stability(p: dict) -> dict:
    """
    Simplified Bishop method (circular slip, homogeneous slope).
    Required: c (kPa), phi (°), gamma (kN/m³), H (m), slope_angle (°)
    Optional: water_table_ratio (0–1, phần trăm chiều cao có nước; default 0)
              radius_ratio (R/H, default 1.5)
    """
    c = float(p['c'])
    phi_deg = float(p['phi'])
    gamma = float(p['gamma'])
    H = float(p['H'])
    beta_deg = float(p['slope_angle'])
    wt_ratio = float(p.get('water_table_ratio', 0))
    R_ratio = float(p.get('radius_ratio', 1.5))

    if H <= 0 or gamma <= 0 or beta_deg <= 0 or beta_deg >= 90:
        raise ValueError("Thông số không hợp lệ.")
    if wt_ratio < 0 or wt_ratio > 1:
        raise ValueError("water_table_ratio phải trong [0, 1].")

    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    R = R_ratio * H

    # Approximate Fellenius method for a single representative slice
    # Assumes a slip circle; realistic for prelim design only
    gamma_w = 9.81  # kN/m³
    theta = beta / 2  # approximate slice mid-angle
    W = 0.5 * gamma * H ** 2 / math.tan(beta)
    L = math.pi * R * beta_deg / 90  # arc length approximation
    u = wt_ratio * gamma_w * H * 0.5  # average pore pressure
    N = W * math.cos(theta) - u * L
    T = W * math.sin(theta)

    if T <= 0:
        raise ValueError("Góc mái dốc quá nhỏ, T ≤ 0.")

    FS = (c * L + N * math.tan(phi)) / T

    # Taylor stability chart approximation (rough check)
    Ns = c / (gamma * H)
    FS_taylor = Ns * (5.52 + 4.0 * math.tan(phi)) / math.sin(beta)

    return {
        "method": "Fellenius (slice đơn, sơ bộ) + kiểm tra biểu đồ Taylor",
        "FS_fellenius": round(FS, 2),
        "FS_taylor_approx": round(FS_taylor, 2),
        "stability_number_Ns": round(Ns, 4),
        "assessment": (
            "Ổn định (FS ≥ 1.5)" if FS >= 1.5 else
            "Cần kiểm tra thêm (1.0 ≤ FS < 1.5)" if FS >= 1.0 else
            "⚠️ Không ổn định (FS < 1.0)"
        ),
        "note": "Đây là tính toán sơ bộ. Thiết kế chính thức cần phần mềm SLOPE/W hoặc PLAXIS với nhiều mặt trượt.",
    }


def _spt_correlation(p: dict) -> dict:
    """
    SPT N-value → soil parameters.
    Required: N (blow count, 1–100), soil_type ('sand'|'clay'|'silt')
    Optional: effective_stress_kPa (default 100), energy_ratio (default 0.6 for 60%)
    """
    N = int(p['N'])
    soil = p.get('soil_type', 'sand').lower()
    sig_v = float(p.get('effective_stress_kPa', 100))
    ER = float(p.get('energy_ratio', 0.6))

    if not 1 <= N <= 100:
        raise ValueError("N phải trong khoảng 1–100.")
    if soil not in ('sand', 'clay', 'silt'):
        raise ValueError("soil_type phải là 'sand', 'clay' hoặc 'silt'.")

    # Normalize to 60% energy
    N60 = N * ER / 0.6
    # Overburden correction (Liao & Whitman 1986)
    CN = min(math.sqrt(100.0 / max(sig_v, 10)), 2.0)
    N1_60 = N60 * CN

    result = {
        "N_raw": N,
        "N60": round(N60, 1),
        "N1_60": round(N1_60, 1),
        "CN": round(CN, 3),
    }

    if soil == 'sand':
        # Peck (1974) relative density
        Dr = min(math.sqrt(N1_60 / 0.92), 1.0) * 100
        # Wolff (1989) friction angle
        phi = 27.1 + 0.3 * N1_60 - 0.00054 * N1_60 ** 2
        phi = min(max(phi, 25), 45)
        result.update({
            "Dr_%": round(Dr, 1),
            "phi_deg": round(phi, 1),
            "consistency": (
                "Rất rời rạc" if N < 4 else "Rời rạc" if N < 10 else
                "Vừa" if N < 30 else "Chặt" if N < 50 else "Rất chặt"
            ),
        })
    else:  # clay / silt
        # Su from N (Terzaghi & Peck 1967): Su ≈ N/16 to N/8 tons/ft² → N·6 kPa (approx)
        Su = N * 6.25  # kPa (conservative)
        result.update({
            "Su_kPa": round(Su, 1),
            "consistency": (
                "Rất mềm" if N < 2 else "Mềm" if N < 4 else
                "Vừa" if N < 8 else "Cứng" if N < 15 else
                "Rất cứng" if N < 30 else "Cứng như đá"
            ),
        })

    return result


def _mohr_coulomb(p: dict) -> dict:
    """
    Mohr-Coulomb: check if a stress state is safe, compute failure envelope.
    Required: c (kPa), phi (°)
    Optional: sigma1 (kPa, major principal), sigma3 (kPa, minor principal)
              tau_applied (kPa), sigma_n (kPa, normal stress)
    """
    c = float(p['c'])
    phi_deg = float(p['phi'])
    phi = math.radians(phi_deg)

    result = {
        "c_kPa": c,
        "phi_deg": phi_deg,
        "formula": "τ_f = c + σ_n · tan(φ)",
    }

    if 'sigma1' in p and 'sigma3' in p:
        s1 = float(p['sigma1'])
        s3 = float(p['sigma3'])
        # Failure criterion: (σ1 - σ3)/2 = c·cos(φ) + (σ1+σ3)/2 · sin(φ)
        lhs = (s1 - s3) / 2
        rhs = c * math.cos(phi) + (s1 + s3) / 2 * math.sin(phi)
        FS = rhs / lhs if lhs > 0 else float('inf')
        sigma_n = (s1 + s3) / 2
        tau = (s1 - s3) / 2
        tau_failure = c + sigma_n * math.tan(phi)
        result.update({
            "sigma1_kPa": s1, "sigma3_kPa": s3,
            "tau_mobilized_kPa": round(tau, 2),
            "tau_failure_kPa": round(tau_failure, 2),
            "FS": round(FS, 2),
            "safe": FS >= 1.0,
        })

    if 'sigma_n' in p and 'tau_applied' in p:
        sn = float(p['sigma_n'])
        tau_a = float(p['tau_applied'])
        tau_f = c + sn * math.tan(phi)
        FS = tau_f / tau_a if tau_a > 0 else float('inf')
        result.update({
            "sigma_n_kPa": sn,
            "tau_applied_kPa": tau_a,
            "tau_failure_kPa": round(tau_f, 2),
            "FS": round(FS, 2),
            "safe": tau_a <= tau_f,
        })

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

_HANDLERS = {
    'bearing_capacity': _bearing_capacity,
    'settlement': _settlement,
    'earth_pressure': _earth_pressure,
    'slope_stability': _slope_stability,
    'spt_correlation': _spt_correlation,
    'mohr_coulomb': _mohr_coulomb,
}

FORMULAS_HELP = (
    "bearing_capacity: sức chịu tải móng nông (Terzaghi/Meyerhof). "
    "Params: c, phi, gamma, B, Df. Tuỳ chọn: L, method, shape, surcharge_q. | "
    "settlement: độ lún cố kết Terzaghi 1D. "
    "Params: H, e0, Cc, sigma0, delta_sigma. Tuỳ chọn: Cs, sigma_p. | "
    "earth_pressure: áp lực đất chủ động/bị động Rankine. "
    "Params: gamma, H, phi. Tuỳ chọn: c, surcharge. | "
    "slope_stability: hệ số an toàn mái dốc (Fellenius + Taylor). "
    "Params: c, phi, gamma, H, slope_angle. Tuỳ chọn: water_table_ratio, radius_ratio. | "
    "spt_correlation: N-SPT → thông số đất. "
    "Params: N, soil_type (sand/clay/silt). Tuỳ chọn: effective_stress_kPa, energy_ratio. | "
    "mohr_coulomb: bao phá hoại Mohr-Coulomb. "
    "Params: c, phi. Tuỳ chọn: sigma1, sigma3 hoặc sigma_n, tau_applied."
)


def geo_calculate(formula: str, params: str) -> dict:
    """Main entry point called by the agent tool handler."""
    if formula not in _HANDLERS:
        return {
            "error": f"formula '{formula}' không có. Các công thức hỗ trợ: {', '.join(_HANDLERS)}",
            "help": FORMULAS_HELP,
        }
    if not isinstance(params, str) or len(params) > 4000:
        return {"error": "params phải là chuỗi JSON tối đa 4000 ký tự."}
    try:
        p = json.loads(params)
    except json.JSONDecodeError as exc:
        return {"error": f"params không phải JSON hợp lệ: {exc}"}
    if not isinstance(p, dict):
        return {"error": "params phải là JSON object."}
    try:
        result = _HANDLERS[formula](p)
    except (KeyError, TypeError, ValueError) as exc:
        return {"error": str(exc), "formula": formula, "help": FORMULAS_HELP}
    result["formula_used"] = formula
    return result
