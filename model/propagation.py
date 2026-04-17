"""Industry-standard radio propagation models for signal prediction.

Models implemented:
  - COST-231 Hata (urban macro-cell, 1500-2000 MHz)
  - Ericsson 9999 (general purpose, calibratable)
  - ITU-R P.1238 (indoor / tunnel attenuation)
  - Free-space path loss (baseline / LOS reference)

References:
  [1] COST 231 Final Report, "Digital Mobile Radio Towards Future Generation Systems"
  [2] Ericsson Radio Systems AB, "Propagation Model 9999"
  [3] ITU-R P.1238-10, "Propagation data for indoor planning"
"""

import math
import numpy as np


# ---------------------------------------------------------------------------
# Free-space path loss (Friis)
# ---------------------------------------------------------------------------

def free_space_loss(freq_mhz: float, dist_km: float) -> float:
    """Free-space path loss in dB.  FSPL = 32.44 + 20*log10(f_MHz) + 20*log10(d_km)"""
    dist_km = max(dist_km, 0.001)
    return 32.44 + 20 * math.log10(freq_mhz) + 20 * math.log10(dist_km)


# ---------------------------------------------------------------------------
# COST-231 Hata model
# ---------------------------------------------------------------------------

def _hata_mobile_correction(freq_mhz: float, hm: float, city_size: str) -> float:
    """Mobile antenna height correction factor a(hm)."""
    if city_size == "large" and freq_mhz >= 400:
        return 3.2 * (math.log10(11.75 * hm)) ** 2 - 4.97
    # Medium/small city
    return (1.1 * math.log10(freq_mhz) - 0.7) * hm - (1.56 * math.log10(freq_mhz) - 0.8)


def cost_231_hata(
    freq_mhz: float,
    hb: float,
    hm: float,
    dist_km: float,
    city_size: str = "large",
) -> float:
    """COST-231 Hata path loss (dB).

    Valid range: 1500-2000 MHz, hb 30-200m, hm 1-10m, d 1-20km.
    Extended here with clamping for near-field use.

    Parameters
    ----------
    freq_mhz : carrier frequency (MHz)
    hb : base station antenna height (m)
    hm : mobile antenna height (m), typically 1.5 for vehicle
    dist_km : link distance (km)
    city_size : "large" (metropolitan) or "medium"
    """
    freq_mhz = max(freq_mhz, 150)
    hb = max(hb, 1.0)
    hm = max(hm, 1.0)
    dist_km = max(dist_km, 0.02)

    ahm = _hata_mobile_correction(freq_mhz, hm, city_size)
    cm = 3.0 if city_size == "large" else 0.0

    pl = (
        46.3
        + 33.9 * math.log10(freq_mhz)
        - 13.82 * math.log10(hb)
        - ahm
        + (44.9 - 6.55 * math.log10(hb)) * math.log10(dist_km)
        + cm
    )
    return pl


# ---------------------------------------------------------------------------
# Ericsson 9999 model
# ---------------------------------------------------------------------------

_ERICSSON_COEFFS = {
    "urban":    (36.2,  30.2,  -12.0, 0.1),
    "suburban": (43.2,  68.93, -12.0, 0.1),
    "rural":    (45.95, 100.6, -12.0, 0.1),
}


def ericsson_9999(
    freq_mhz: float,
    hb: float,
    hm: float,
    dist_km: float,
    environment: str = "urban",
) -> float:
    """Ericsson 9999 path loss model (dB).

    Parameters
    ----------
    freq_mhz : carrier frequency (MHz)
    hb : base station height (m)
    hm : mobile station height (m)
    dist_km : distance (km)
    environment : "urban", "suburban", or "rural"
    """
    freq_mhz = max(freq_mhz, 150)
    hb = max(hb, 1.0)
    hm = max(hm, 1.0)
    dist_km = max(dist_km, 0.02)

    a0, a1, a2, a3 = _ERICSSON_COEFFS.get(environment, _ERICSSON_COEFFS["urban"])
    gf = 44.49 * math.log10(freq_mhz) - 4.78 * (math.log10(freq_mhz)) ** 2

    pl = (
        a0
        + a1 * math.log10(dist_km)
        + a2 * math.log10(hb)
        + a3 * math.log10(hb) * math.log10(dist_km)
        - 3.2 * (math.log10(11.75 * hm)) ** 2
        + gf
    )
    return pl


# ---------------------------------------------------------------------------
# ITU-R P.1238 indoor / structure penetration loss
# ---------------------------------------------------------------------------

def itu_structure_loss(
    freq_mhz: float,
    n_floors: int = 0,
    structure_type: str = "concrete",
) -> float:
    """Extra penetration loss (dB) for indoor/tunnel/underpass.

    structure_type:
      "concrete"     -- heavy concrete (tunnel, underpass) ~25-35 dB
      "dense_urban"  -- urban canyon multipath loss ~8-15 dB
      "light"        -- light building walls ~5-10 dB
    """
    # Base penetration by structure
    base = {"concrete": 28.0, "dense_urban": 10.0, "light": 6.0}
    loss = base.get(structure_type, 10.0)

    # Frequency-dependent component (higher freq = more penetration loss)
    if freq_mhz > 0:
        loss += 4.0 * math.log10(freq_mhz / 900.0)

    # Floor factor
    loss += n_floors * 4.0

    return max(loss, 0.0)


# ---------------------------------------------------------------------------
# Shadow fading (log-normal)
# ---------------------------------------------------------------------------

def shadow_fading(rng: np.random.Generator, sigma_db: float = 8.0) -> float:
    """Log-normal shadow fading sample (dB). Industry standard sigma = 6-10 dB."""
    return abs(float(rng.normal(0, sigma_db)))


# ---------------------------------------------------------------------------
# Rain attenuation (ITU-R P.838 simplified)
# ---------------------------------------------------------------------------

def rain_attenuation(
    freq_mhz: float,
    dist_km: float,
    rain_rate_mmh: float,
) -> float:
    """Simplified rain attenuation (dB).

    Based on ITU-R P.838. Significant above 10 GHz but non-negligible
    at 2-5 GHz in heavy rain (> 25 mm/h).
    """
    if rain_rate_mmh <= 0 or freq_mhz < 1000:
        return 0.0
    freq_ghz = freq_mhz / 1000.0
    # Simplified specific attenuation (dB/km)
    k = 0.0001 * freq_ghz ** 1.6
    alpha = 1.0 + 0.03 * freq_ghz
    gamma = k * (rain_rate_mmh ** alpha)
    return gamma * dist_km


# ---------------------------------------------------------------------------
# Combined model: ensemble of COST-231 + Ericsson + corrections
# ---------------------------------------------------------------------------

def combined_path_loss(
    freq_mhz: float,
    hb: float,
    hm: float,
    dist_km: float,
    environment: str = "urban",
    city_size: str = "large",
    structure_type: str | None = None,
    rain_rate_mmh: float = 0.0,
    rng: np.random.Generator | None = None,
    sigma_db: float = 8.0,
) -> float:
    """Ensemble path loss combining COST-231 Hata and Ericsson 9999.

    Returns total path loss in dB including:
      - Weighted average of COST-231 and Ericsson models (0.55 / 0.45)
      - Structure penetration loss (tunnel, underpass, canyon)
      - Rain attenuation
      - Log-normal shadow fading

    This ensemble approach reduces model bias compared to using a single
    propagation model and is standard practice in radio network planning tools.
    """
    pl_cost = cost_231_hata(freq_mhz, hb, hm, dist_km, city_size)
    pl_eric = ericsson_9999(freq_mhz, hb, hm, dist_km, environment)

    # Weighted ensemble -- COST-231 is more validated for urban India
    pl = 0.55 * pl_cost + 0.45 * pl_eric

    # Structure loss
    if structure_type:
        pl += itu_structure_loss(freq_mhz, structure_type=structure_type)

    # Rain
    if rain_rate_mmh > 0:
        pl += rain_attenuation(freq_mhz, dist_km, rain_rate_mmh)

    # Shadow fading
    if rng is not None:
        pl += shadow_fading(rng, sigma_db)

    return pl


# ---------------------------------------------------------------------------
# Received signal strength
# ---------------------------------------------------------------------------

def received_signal_dbm(
    tx_power_dbm: float,
    freq_mhz: float,
    hb: float,
    hm: float,
    dist_km: float,
    environment: str = "urban",
    city_size: str = "large",
    structure_type: str | None = None,
    rain_rate_mmh: float = 0.0,
    rng: np.random.Generator | None = None,
    sigma_db: float = 8.0,
) -> float:
    """Compute received signal strength in dBm.

    rx_power = tx_power - path_loss
    """
    pl = combined_path_loss(
        freq_mhz, hb, hm, dist_km, environment, city_size,
        structure_type, rain_rate_mmh, rng, sigma_db,
    )
    return tx_power_dbm - pl


def dbm_to_quality(rx_dbm: float) -> float:
    """Map received power (dBm) to quality score 0-100.

    Mapping calibrated to real-world LTE thresholds:
      >= -65 dBm  -> 100 (excellent)
      -65 to -75  ->  80-100 (good)
      -75 to -85  ->  60-80 (fair)
      -85 to -100 ->  30-60 (poor)
      -100 to -115 -> 5-30 (very poor)
      < -115      ->  0 (no service)
    """
    if rx_dbm >= -65:
        return 100.0
    elif rx_dbm >= -75:
        return 80.0 + (rx_dbm + 75) * 2.0
    elif rx_dbm >= -85:
        return 60.0 + (rx_dbm + 85) * 2.0
    elif rx_dbm >= -100:
        return 30.0 + (rx_dbm + 100) * 2.0
    elif rx_dbm >= -115:
        return 5.0 + (rx_dbm + 115) * (25.0 / 15.0)
    else:
        return 0.0
