"""
Era-specific pillar configurations for extended backtesting (1907-2025).

When backtesting pre-1962, many modern indicators don't exist.  Each era
defines which pillars have real data and what defaults apply for unavailable
pillars.  The era configuration also specifies threshold adjustments because
historical volatility regimes and credit market structures differ materially
from the modern period.

Era boundaries are based on structural breaks in the data record:
  1907-1913  Pre-Fed:              No central bank, gold standard
  1913-1919  Early Fed / WWI:      Fed opens, wartime controls
  1919-1934  Interwar / Depression: Moody's credit data begins, 1929 crash
  1934-1954  New Deal / WWII:      T-Bills issued, SEC created, Bretton Woods
  1954-1971  Post-War / Bretton W.: Fed Funds daily, modern Treasury market
  1971-1990  Post-Bretton Woods:    Floating rates, NASDAQ (realized vol)
  1990-1997  Modern (early):        VIX introduced, global markets
  1997-2006  Modern (middle):       TED spread, CP spread, ICE BofA indices
  2006-2018  Modern (pre-SOFR):     Full data, LIBOR-OIS, SVXY
  2018-present  Modern (SOFR):      Full data, SOFR-IORB
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Era boundary dates
# ─────────────────────────────────────────────────────────────────────────────

ERA_BOUNDARIES = {
    "pre_fed":          (datetime(1907, 1, 1), datetime(1913, 11, 15)),
    "early_fed_wwi":    (datetime(1913, 11, 16), datetime(1919, 12, 31)),
    "interwar":         (datetime(1920, 1, 1), datetime(1934, 5, 31)),
    "new_deal_wwii":    (datetime(1934, 6, 1), datetime(1954, 6, 30)),
    "post_war":         (datetime(1954, 7, 1), datetime(1971, 2, 4)),
    "post_bretton":     (datetime(1971, 2, 5), datetime(1990, 1, 1)),
    "modern_early":     (datetime(1990, 1, 2), datetime(1996, 12, 31)),
    "modern_mid":       (datetime(1997, 1, 1), datetime(2005, 12, 31)),
    "modern_pre_sofr":  (datetime(2006, 1, 1), datetime(2018, 4, 2)),
    "modern_sofr":      (datetime(2018, 4, 3), datetime(2099, 12, 31)),
}


def get_era(date: datetime) -> str:
    """Return the era name for a given date."""
    for era_name, (start, end) in ERA_BOUNDARIES.items():
        if start <= date <= end:
            return era_name
    if date < datetime(1907, 1, 1):
        return "pre_data"
    return "modern_sofr"


# ─────────────────────────────────────────────────────────────────────────────
# Per-pillar availability flags  (True = real data available for this era)
# ─────────────────────────────────────────────────────────────────────────────

PILLAR_AVAILABILITY = {
    #                   liq  val  vol  pol  pos  cnt  prc
    "pre_fed":         (True, True, True, False, False, True, False),
    "early_fed_wwi":   (True, True, True, True,  False, True, False),
    "interwar":        (True, True, True, True,  True,  True, False),
    "new_deal_wwii":   (True, True, True, True,  True,  True, False),
    "post_war":        (True, True, True, True,  True,  True, False),
    "post_bretton":    (True, True, True, True,  True,  True, False),
    "modern_early":    (True, True, True, True,  True,  True, False),
    "modern_mid":      (True, True, True, True,  True,  True, False),
    "modern_pre_sofr": (True, True, True, True,  True,  True, True),
    "modern_sofr":     (True, True, True, True,  True,  True, True),
}

_PILLAR_NAMES = (
    "liquidity", "valuation", "volatility", "policy",
    "positioning", "contagion", "private_credit",
)


def get_available_pillars(date: datetime) -> dict[str, bool]:
    """Return a dict mapping pillar name → availability for *date*."""
    era = get_era(date)
    flags = PILLAR_AVAILABILITY.get(era, (True,) * 7)
    return dict(zip(_PILLAR_NAMES, flags))


# ─────────────────────────────────────────────────────────────────────────────
# Default pillar scores when no data is available
# ─────────────────────────────────────────────────────────────────────────────
# Design principle: default to *neutral-to-slightly-cautious* so that
# absent pillars neither mask crises nor create false alarms.

DEFAULT_PILLAR_SCORES = {
    # Positioning: no CFTC/basis trade data → neutral 0.50
    "positioning": 0.50,
    # Private Credit: no BDC/SLOOS pre-2004 → slightly cautious 0.52
    "private_credit": 0.52,
    # Policy: pre-Fed (no central bank) → structurally penalised
    # (override handled specially in get_policy_default)
    "policy": 0.35,
    # Contagion: pre-Bretton-Woods → use GBP-USD gold parity deviation
    # but if truly unavailable → neutral 0.50
    "contagion": 0.50,
}


def get_default_score(pillar: str, date: datetime) -> float:
    """
    Return the default score for a pillar that lacks data on *date*.

    Special cases:
    - Policy pre-1913: no central bank → 0.25 (structurally constrained)
    - Policy 1913-1934: early Fed, limited toolkit → 0.35
    - Positioning pre-1919: no margin data → 0.50
    - Positioning 1919-1954: FINRA margin debt exists → 0.50 still
      (margin_debt_to_gdp is incorporated via the data proxy, not the
       default)
    - Private Credit pre-2004: → 0.52 (slightly cautious)
    """
    if pillar == "policy":
        if date < datetime(1913, 11, 16):
            return 0.25  # No lender of last resort
        elif date < datetime(1934, 6, 1):
            return 0.35  # Early Fed, limited tools
        else:
            return 0.50  # Should have real data
    return DEFAULT_PILLAR_SCORES.get(pillar, 0.50)


# ─────────────────────────────────────────────────────────────────────────────
# Era-specific threshold overrides
# ─────────────────────────────────────────────────────────────────────────────
# Some thresholds need widening for early eras because market structure
# was fundamentally different:
#   - Pre-1913: no Fed, call money rate spiked to 100%+ routinely
#   - 1913-1934: discount rate is primary tool, not fed funds
#   - 1907-1919: railroad bonds as credit proxy (wider typical spreads)

@dataclass
class EraThresholdOverrides:
    """Threshold adjustments for a specific era."""

    era_name: str

    # Liquidity: widen thresholds for eras with structurally wider spreads
    liquidity_spread_breach_bps: Optional[float] = None  # None = use calibrated default

    # Valuation: railroad bond spreads were wider than modern IG/HY
    ig_oas_breach_high_bps: Optional[float] = None
    hy_oas_breach_high_bps: Optional[float] = None

    # Volatility: Schwert vol is annualised, typically higher than VIX
    vix_breach_high: Optional[float] = None
    vix_ample_high: Optional[float] = None

    # Policy: policy room interpretation changes pre-Fed
    policy_room_breach_bps: Optional[float] = None

    # Weight adjustments: pillars with proxy data get lower weight
    pillar_weight_overrides: dict[str, float] = field(default_factory=dict)


ERA_THRESHOLD_OVERRIDES: dict[str, EraThresholdOverrides] = {
    "pre_fed": EraThresholdOverrides(
        era_name="pre_fed",
        liquidity_spread_breach_bps=200,   # Call money spikes were routine
        ig_oas_breach_high_bps=600,        # Railroad bonds wider spread
        hy_oas_breach_high_bps=1500,       # Much wider for railroad HY proxy
        vix_breach_high=50,                # Schwert vol was structurally higher
        vix_ample_high=28,
        policy_room_breach_bps=None,       # No policy pillar pre-Fed
        pillar_weight_overrides={
            "liquidity": 0.25,
            "valuation": 0.25,
            "volatility": 0.20,
            "contagion": 0.15,
            "positioning": 0.15,  # Default score
        },
    ),
    "early_fed_wwi": EraThresholdOverrides(
        era_name="early_fed_wwi",
        liquidity_spread_breach_bps=150,
        ig_oas_breach_high_bps=500,
        hy_oas_breach_high_bps=1400,
        vix_breach_high=50,
        vix_ample_high=28,
        policy_room_breach_bps=50,         # Fed discount rate only
        pillar_weight_overrides={
            "liquidity": 0.20,
            "valuation": 0.20,
            "volatility": 0.18,
            "policy": 0.17,
            "contagion": 0.15,
            "positioning": 0.10,  # Default score
        },
    ),
    "interwar": EraThresholdOverrides(
        era_name="interwar",
        liquidity_spread_breach_bps=100,
        ig_oas_breach_high_bps=500,
        hy_oas_breach_high_bps=1400,
        vix_breach_high=45,
        vix_ample_high=25,
        policy_room_breach_bps=40,
        pillar_weight_overrides={
            "liquidity": 0.18,
            "valuation": 0.18,
            "volatility": 0.17,
            "policy": 0.17,
            "positioning": 0.15,  # FINRA margin debt
            "contagion": 0.15,
        },
    ),
    "new_deal_wwii": EraThresholdOverrides(
        era_name="new_deal_wwii",
        liquidity_spread_breach_bps=60,
        ig_oas_breach_high_bps=450,
        hy_oas_breach_high_bps=1200,
        vix_breach_high=42,
        vix_ample_high=24,
        policy_room_breach_bps=35,
        pillar_weight_overrides={
            "liquidity": 0.17,
            "valuation": 0.17,
            "volatility": 0.17,
            "policy": 0.17,
            "positioning": 0.16,
            "contagion": 0.16,
        },
    ),
    "post_war": EraThresholdOverrides(
        era_name="post_war",
        # Modern-ish thresholds from here; minor widening
        ig_oas_breach_high_bps=420,
        hy_oas_breach_high_bps=1100,
        vix_breach_high=42,
        pillar_weight_overrides={},  # Use defaults (1/7 each)
    ),
}


def get_era_overrides(date: datetime) -> Optional[EraThresholdOverrides]:
    """Return threshold overrides for the era containing *date*, or None."""
    era = get_era(date)
    return ERA_THRESHOLD_OVERRIDES.get(era)


# ─────────────────────────────────────────────────────────────────────────────
# Weight calculation for eras with missing pillars
# ─────────────────────────────────────────────────────────────────────────────

def get_era_weights(date: datetime) -> dict[str, float]:
    """
    Return pillar weights for the given date.

    For modern eras, returns equal 1/7 weights.  For earlier eras, uses
    custom weights that down-weight pillars relying on proxy data or
    defaults.  Missing-data pillars still get a weight (using their
    default score) but at reduced influence.
    """
    overrides = get_era_overrides(date)

    if overrides and overrides.pillar_weight_overrides:
        weights = overrides.pillar_weight_overrides.copy()
        # Ensure all 7 pillars present
        for p in _PILLAR_NAMES:
            if p not in weights:
                weights[p] = 1.0 / 7.0
        # Normalise to sum = 1
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
    else:
        return {p: 1.0 / 7.0 for p in _PILLAR_NAMES}
