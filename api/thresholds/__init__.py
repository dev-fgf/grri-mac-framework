import json
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    thresholds = {
        "liquidity": {
            "sofr_iorb": {"ample": 2, "thin": 8, "breach": 15},
            "cp_treasury": {"ample": 15, "thin": 40, "breach": 80},
            "cross_currency": {"ample": -15, "thin": -35, "breach": -60},
            "bid_ask": {"ample": 0.5, "thin": 1.5, "breach": 4.0}
        },
        "valuation": {
            "term_premium": {"ample": 100, "thin": 25, "breach": -50},
            "ig_oas": {"ample": 150, "thin": 90, "breach": 60},
            "hy_oas": {"ample": 500, "thin": 350, "breach": 250}
        },
        "positioning": {
            "basis_trade": {"ample": 300, "thin": 550, "breach": 750},
            "spec_net_percentile": {
                "ample_low": 35, "ample_high": 65,
                "thin_low": 18, "thin_high": 82,
                "breach_low": 5, "breach_high": 95
            },
            "svxy_aum": {"ample": 350, "thin": 600, "breach": 850}
        },
        "volatility": {
            "vix_level": {
                "ample_low": 12, "ample_high": 18,
                "thin_low": 8, "thin_high": 28,
                "breach_low": 0, "breach_high": 40
            },
            "term_structure": {
                "ample_low": 0.98, "ample_high": 1.08,
                "thin_low": 0.92, "thin_high": 1.15,
                "breach_low": 0.80, "breach_high": 1.25
            },
            "rv_iv_gap": {"ample": 3, "thin": 8, "breach": 15}
        },
        "policy": {
            "fed_funds_vs_neutral": {"ample": 25, "thin": 100, "breach": 200},
            "balance_sheet_gdp": {"ample": 20, "thin": 30, "breach": 38},
            "core_pce_vs_target": {"ample": 30, "thin": 80, "breach": 150}
        }
    }

    return func.HttpResponse(
        json.dumps(thresholds),
        mimetype="application/json"
    )
