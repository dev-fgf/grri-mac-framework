"""Crisis visualization module for MAC framework.

Generates time-series plots comparing MAC scores with VIX and other indicators
during historical crisis periods to illustrate the framework's advantages.

Usage:
    python -m grri_mac.visualization.crisis_plots

Or programmatically:
    from grri_mac.visualization import generate_all_crisis_figures
    generate_all_crisis_figures(output_dir="figures/")
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

# Try to import matplotlib, provide fallback message if not available
try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.lines import Line2D
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Run: pip install matplotlib")

from ..backtest.scenarios import KNOWN_EVENTS
from ..backtest.calibrated_engine import CalibratedBacktestEngine


@dataclass
class CrisisWindow:
    """Defines a crisis period for visualization."""
    name: str
    start_date: datetime
    peak_date: datetime
    end_date: datetime
    mac_score: float
    vix_peak: float
    breaches: list[str]
    hedge_worked: bool
    description: str


# Define crisis windows with surrounding context
CRISIS_WINDOWS = {
    "lehman_2008": CrisisWindow(
        name="Lehman Brothers Collapse",
        start_date=datetime(2008, 8, 1),
        peak_date=datetime(2008, 9, 15),
        end_date=datetime(2008, 11, 30),
        mac_score=0.141,
        vix_peak=80.86,
        breaches=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        hedge_worked=True,
        description="Global Financial Crisis peak - maximum stress across all pillars",
    ),
    "covid_2020": CrisisWindow(
        name="COVID-19 Market Crash",
        start_date=datetime(2020, 2, 15),
        peak_date=datetime(2020, 3, 16),
        end_date=datetime(2020, 4, 30),
        mac_score=0.146,
        vix_peak=82.69,
        breaches=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        hedge_worked=False,
        description="Pandemic shock - Treasury hedge failed due to positioning breach",
    ),
    "volmageddon_2018": CrisisWindow(
        name="Volmageddon",
        start_date=datetime(2018, 1, 15),
        peak_date=datetime(2018, 2, 5),
        end_date=datetime(2018, 3, 15),
        mac_score=0.477,
        vix_peak=50.30,
        breaches=["positioning", "volatility"],
        hedge_worked=True,
        description="VIX spike caused by short-vol unwind - moderate stress",
    ),
    "repo_spike_2019": CrisisWindow(
        name="Repo Market Spike",
        start_date=datetime(2019, 9, 1),
        peak_date=datetime(2019, 9, 17),
        end_date=datetime(2019, 10, 15),
        mac_score=0.630,
        vix_peak=18.56,
        breaches=["liquidity"],
        hedge_worked=True,
        description="Repo rate spike - localized liquidity stress, VIX barely moved",
    ),
    "svb_2023": CrisisWindow(
        name="SVB/Banking Crisis",
        start_date=datetime(2023, 2, 15),
        peak_date=datetime(2023, 3, 10),
        end_date=datetime(2023, 4, 15),
        mac_score=0.423,
        vix_peak=26.52,
        breaches=["liquidity"],
        hedge_worked=True,
        description="Regional bank stress - moderate VIX, liquidity concerns",
    ),
    "tariff_2025": CrisisWindow(
        name="April Tariff Shock",
        start_date=datetime(2025, 3, 15),
        peak_date=datetime(2025, 4, 2),
        end_date=datetime(2025, 5, 1),
        mac_score=0.435,
        vix_peak=45.0,
        breaches=["positioning"],
        hedge_worked=False,
        description="Tariff escalation - positioning breach predicted hedge failure",
    ),
}


class CrisisVisualizer:
    """Generates visualizations for MAC framework crisis analysis."""

    def __init__(self, output_dir: str = "figures"):
        """Initialize visualizer.

        Args:
            output_dir: Directory to save generated figures
        """
        self.output_dir = output_dir
        self.engine = CalibratedBacktestEngine()

        # Color scheme
        self.colors = {
            "mac": "#1f77b4",      # Blue
            "vix": "#ff7f0e",      # Orange
            "ample": "#2ca02c",    # Green
            "thin": "#ffbb00",     # Yellow
            "stretched": "#ff7f0e",  # Orange
            "breach": "#d62728",   # Red
            "hedge_fail": "#9467bd",  # Purple
        }

        # Pillar colors
        self.pillar_colors = {
            "liquidity": "#1f77b4",
            "valuation": "#ff7f0e",
            "positioning": "#2ca02c",
            "volatility": "#d62728",
            "policy": "#9467bd",
            "contagion": "#8c564b",
        }

        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib required for visualization")

    def _ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def plot_mac_vs_vix_conceptual(
        self,
        save: bool = True,
        filename: str = "mac_vs_vix_conceptual.png",
    ) -> Optional[plt.Figure]:
        """
        Create conceptual diagram showing MAC vs VIX during different crisis types.

        This illustrates the key advantage: MAC captures stress dimensions VIX misses.
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("MAC vs VIX: Capturing Different Stress Dimensions",
                     fontsize=14, fontweight='bold')

        # Define scenarios to plot
        scenarios = [
            {"title": "Lehman 2008: Both Signals Aligned",
             "mac_series": [0.65, 0.55, 0.40, 0.25, 0.14, 0.18, 0.25, 0.35],
             "vix_series": [25, 35, 45, 60, 81, 70, 55, 40],
             "ax": axes[0, 0],
             "note": "Systemic crisis: MAC and VIX both spike", },
            {"title": "Repo Spike 2019: MAC Detects, VIX Misses",
             "mac_series": [0.75, 0.70, 0.63, 0.55, 0.63, 0.68, 0.72, 0.75],
             "vix_series": [14, 15, 16, 19, 17, 15, 14, 13],
             "ax": axes[0, 1],
             "note":
             "Funding crisis: MAC catches liquidity"
             " stress\nVIX stays calm"
             " (equity markets stable)", },
            {"title": "COVID-19 2020: Hedge Failure Warning",
             "mac_series": [0.70, 0.55, 0.35, 0.15, 0.20, 0.35, 0.50, 0.60],
             "vix_series": [15, 30, 55, 83, 65, 45, 30, 22],
             "ax": axes[1, 0],
             "note":
             "Positioning breach -> Treasury hedge FAILED\nMAC warned of the structural break", },
            {"title": "Flash Crash 2010: VIX Spike, MAC Moderate",
             "mac_series": [0.60, 0.55, 0.45, 0.42, 0.50, 0.58, 0.62, 0.65],
             "vix_series": [18, 22, 35, 42, 28, 22, 19, 17],
             "ax": axes[1, 1],
             "note": "Technical event: VIX spiked briefly\nMAC showed limited systemic stress", },]

        for scenario in scenarios:
            ax = scenario["ax"]
            days = list(range(len(scenario["mac_series"])))

            # Plot MAC (inverted for visual alignment - lower MAC = more stress)
            ax2 = ax.twinx()

            line1 = ax.plot(days, scenario["mac_series"],
                            color=self.colors["mac"], linewidth=2.5,
                            marker='o', markersize=6, label="MAC Score")
            ax.axhline(y=0.2, color=self.colors["breach"], linestyle='--',
                       alpha=0.7, label="MAC Breach Level")
            ax.fill_between(days, 0, 0.2, color=self.colors["breach"], alpha=0.1)

            # Plot VIX
            line2 = ax2.plot(days, scenario["vix_series"],
                             color=self.colors["vix"], linewidth=2.5,
                             marker='s', markersize=6, label="VIX")
            ax2.axhline(y=30, color=self.colors["vix"], linestyle=':',
                        alpha=0.5, label="VIX Warning (30)")

            ax.set_title(scenario["title"], fontsize=11, fontweight='bold')
            ax.set_xlabel("Days from Crisis Start")
            ax.set_ylabel("MAC Score", color=self.colors["mac"])
            ax2.set_ylabel("VIX Level", color=self.colors["vix"])

            ax.set_ylim(0, 1)
            ax2.set_ylim(0, 100)

            ax.tick_params(axis='y', labelcolor=self.colors["mac"])
            ax2.tick_params(axis='y', labelcolor=self.colors["vix"])

            # Add annotation
            ax.text(0.02, 0.02, scenario["note"], transform=ax.transAxes,
                    fontsize=8, verticalalignment='bottom',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            # Combined legend
            lines = line1 + line2
            labels = [line.get_label() for line in lines]
            ax.legend(lines, labels, loc='upper right', fontsize=8)

        plt.tight_layout()

        if save:
            self._ensure_output_dir()
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"Saved: {filepath}")

        return fig

    def plot_pillar_breakdown(
        self,
        crisis_key: str,
        save: bool = True,
    ) -> Optional[plt.Figure]:
        """
        Create stacked bar chart showing pillar contributions during a crisis.

        Args:
            crisis_key: Key from KNOWN_EVENTS
            save: Whether to save the figure
        """
        if crisis_key not in KNOWN_EVENTS:
            print(f"Unknown crisis: {crisis_key}")
            return None

        scenario = KNOWN_EVENTS[crisis_key]
        result = self.engine.run_scenario(scenario)

        fig, ax = plt.subplots(figsize=(10, 6))

        pillars = list(result.pillar_scores.keys())
        scores = list(result.pillar_scores.values())
        colors = [self.pillar_colors.get(p, "#999999") for p in pillars]

        # Horizontal bar chart
        bars = ax.barh(pillars, scores, color=colors, edgecolor='black', linewidth=0.5)

        # Add breach threshold line
        ax.axvline(x=0.2, color=self.colors["breach"], linestyle='--',
                   linewidth=2, label="Breach Threshold (0.2)")

        # Color bars below breach threshold
        for bar, score, pillar in zip(bars, scores, pillars):
            if score < 0.2:
                bar.set_edgecolor(self.colors["breach"])
                bar.set_linewidth(3)
                bar.set_hatch('///')

        # Add score labels
        for bar, score in zip(bars, scores):
            width = bar.get_width()
            ax.text(width + 0.02, bar.get_y() + bar.get_height()/2,
                    f'{score:.3f}', va='center', fontsize=10, fontweight='bold')

        ax.set_xlabel("Pillar Score (0 = Breached, 1 = Ample)", fontsize=11)
        ax.set_title(f"MAC Pillar Breakdown: {scenario.name}\n"
                     f"Date: {scenario.date.strftime('%Y-%m-%d')} | "
                     f"MAC: {result.mac_score:.3f} | "
                     f"Hedge: {'Worked' if scenario.treasury_hedge_worked else 'FAILED'}",
                     fontsize=12, fontweight='bold')

        ax.set_xlim(0, 1.15)
        ax.legend(loc='lower right')

        # Add zone labels
        ax.axvspan(0, 0.2, alpha=0.1, color='red', label='Breach Zone')
        ax.axvspan(0.2, 0.5, alpha=0.1, color='orange')
        ax.axvspan(0.5, 0.8, alpha=0.1, color='yellow')
        ax.axvspan(0.8, 1.15, alpha=0.1, color='green')

        # Zone labels at top
        ax.text(0.1, len(pillars) + 0.3, 'BREACH', ha='center', fontsize=8, color='red')
        ax.text(0.35, len(pillars) + 0.3, 'STRETCHED', ha='center', fontsize=8, color='orange')
        ax.text(0.65, len(pillars) + 0.3, 'THIN', ha='center', fontsize=8, color='#888800')
        ax.text(0.9, len(pillars) + 0.3, 'AMPLE', ha='center', fontsize=8, color='green')

        plt.tight_layout()

        if save:
            self._ensure_output_dir()
            filename = f"pillar_breakdown_{crisis_key}.png"
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"Saved: {filepath}")

        return fig

    def plot_crisis_comparison(
        self,
        save: bool = True,
        filename: str = "crisis_comparison.png",
    ) -> Optional[plt.Figure]:
        """
        Create scatter plot comparing MAC vs VIX across all crisis events.

        Illustrates that MAC provides orthogonal information to VIX.
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        # Collect data from all scenarios
        for key, scenario in KNOWN_EVENTS.items():
            result = self.engine.run_scenario(scenario)

            vix = scenario.indicators.get("vix_level", 30)
            mac = result.mac_score
            hedge_worked = scenario.treasury_hedge_worked

            # Plot point
            color = self.colors["ample"] if hedge_worked else self.colors["hedge_fail"]
            marker = 'o' if hedge_worked else 'X'
            size = 200 if not hedge_worked else 120

            ax.scatter(vix, mac, c=color, s=size, marker=marker,
                       edgecolors='black', linewidth=1.5, zorder=5)

            # Label
            label = scenario.name.replace(" ", "\n")[:25]
            ax.annotate(label, (vix, mac),
                        xytext=(8, 8), textcoords='offset points',
                        fontsize=8, alpha=0.8)

        # Add quadrant lines
        ax.axhline(y=0.35, color='gray', linestyle='--', alpha=0.5)
        ax.axvline(x=30, color='gray', linestyle='--', alpha=0.5)

        # Quadrant labels
        ax.text(15, 0.7, "Low VIX, High MAC\n(Hidden Fragility)",
                ha='center', fontsize=9, style='italic', alpha=0.7)
        ax.text(60, 0.7, "High VIX, High MAC\n(Transient Shock)",
                ha='center', fontsize=9, style='italic', alpha=0.7)
        ax.text(15, 0.15, "Low VIX, Low MAC\n(Rare)",
                ha='center', fontsize=9, style='italic', alpha=0.7)
        ax.text(60, 0.15, "High VIX, Low MAC\n(Systemic Crisis)",
                ha='center', fontsize=9, style='italic', alpha=0.7)

        # Add breach zone
        ax.axhspan(0, 0.2, alpha=0.15, color='red')
        ax.text(5, 0.1, "MAC BREACH ZONE", fontsize=8, color='red', fontweight='bold')

        ax.set_xlabel("VIX Level", fontsize=12)
        ax.set_ylabel("MAC Score", fontsize=12)
        ax.set_title("MAC vs VIX Across 14 Crisis Events (1998-2025)\n"
                     "X = Treasury Hedge Failed | O = Hedge Worked",
                     fontsize=13, fontweight='bold')

        ax.set_xlim(0, 100)
        ax.set_ylim(0, 0.85)

        # Custom legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor=self.colors["ample"],
                   markersize=10, label='Hedge Worked'),
            Line2D([0], [0], marker='X', color='w', markerfacecolor=self.colors["hedge_fail"],
                   markersize=12, label='Hedge FAILED'),
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()

        if save:
            self._ensure_output_dir()
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"Saved: {filepath}")

        return fig

    def plot_positioning_hedge_relationship(
        self,
        save: bool = True,
        filename: str = "positioning_hedge_relationship.png",
    ) -> Optional[plt.Figure]:
        """
        Create visualization showing the positioning-hedge failure relationship.

        This is the key insight: positioning breach predicts hedge failure.
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        # Collect data
        scenarios_data: list[dict[str, Any]] = []
        for key, scenario in KNOWN_EVENTS.items():
            result = self.engine.run_scenario(scenario)
            pos_score = result.pillar_scores.get("positioning", 0.5)
            scenarios_data.append({
                "name": scenario.name,
                "date": scenario.date,
                "positioning": pos_score,
                "hedge_worked": scenario.treasury_hedge_worked,
                "breaches": result.breach_flags,
            })

        # Sort by date
        scenarios_data.sort(key=lambda x: x["date"])

        # Plot
        x_positions = range(len(scenarios_data))
        for i, data in enumerate(scenarios_data):
            color = self.colors["ample"] if data["hedge_worked"] else self.colors["hedge_fail"]
            marker = 'o' if data["hedge_worked"] else 'X'
            size = 200 if not data["hedge_worked"] else 150

            ax.scatter(i, data["positioning"], c=color, s=size, marker=marker,
                       edgecolors='black', linewidth=2, zorder=5)

        # Add breach threshold
        ax.axhline(y=0.2, color=self.colors["breach"], linestyle='--',
                   linewidth=2, label="Breach Threshold (0.2)")
        ax.fill_between(x_positions, 0, 0.2, color=self.colors["breach"], alpha=0.15)

        # Connect points with line
        positions = [d["positioning"] for d in scenarios_data]
        ax.plot(x_positions, positions, color='gray', alpha=0.3, linestyle='-', zorder=1)

        # Labels
        ax.set_xticks(x_positions)
        ax.set_xticklabels([d["date"].strftime("%Y") + "\n" + d["name"][:15]
                            for d in scenarios_data],
                           rotation=45, ha='right', fontsize=8)

        ax.set_ylabel("Positioning Pillar Score", fontsize=12)
        ax.set_title("Key Insight: Positioning Breach Predicts Treasury Hedge Failure\n"
                     "100% Correlation in Historical Sample (1998-2025)",
                     fontsize=13, fontweight='bold')

        ax.set_ylim(0, 1)

        # Annotation boxes for failed hedges
        for i, data in enumerate(scenarios_data):
            if not data["hedge_worked"]:
                ax.annotate(
                    "HEDGE\nFAILED",
                    (i, data["positioning"]),
                    xytext=(0, -40), textcoords='offset points',
                    ha='center', fontsize=8, fontweight='bold',
                    color=self.colors["hedge_fail"],
                    bbox=dict(boxstyle='round', facecolor='white',
                              edgecolor=self.colors["hedge_fail"]),
                    arrowprops=dict(arrowstyle='->', color=self.colors["hedge_fail"])
                )

        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor=self.colors["ample"],
                   markersize=10, markeredgecolor='black', label='Hedge Worked'),
            Line2D([0], [0], marker='X', color='w', markerfacecolor=self.colors["hedge_fail"],
                   markersize=12, markeredgecolor='black', label='Hedge FAILED'),
            Line2D([0], [0], color=self.colors["breach"], linestyle='--',
                   linewidth=2, label='Breach Threshold'),
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()

        if save:
            self._ensure_output_dir()
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"Saved: {filepath}")

        return fig

    def plot_mac_heatmap(
        self,
        save: bool = True,
        filename: str = "mac_pillar_heatmap.png",
    ) -> Optional[plt.Figure]:
        """
        Create heatmap showing pillar scores across all crisis events.
        """
        # Collect data
        scenarios: list[dict[str, Any]] = []
        pillar_names = ["liquidity", "valuation",
                        "positioning", "volatility", "policy", "contagion"]

        for key, scenario in KNOWN_EVENTS.items():
            result = self.engine.run_scenario(scenario)
            scenarios.append({
                "name": f"{scenario.date.year} {scenario.name[:20]}",
                "scores": [result.pillar_scores.get(p, 0.5) for p in pillar_names],
                "mac": result.mac_score,
                "hedge": scenario.treasury_hedge_worked,
            })

        # Sort by date (extracted from name)
        scenarios.sort(key=lambda x: x["name"])

        fig, ax = plt.subplots(figsize=(14, 10))

        # Create matrix
        data = [s["scores"] for s in scenarios]

        # Plot heatmap
        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)

        # Labels
        ax.set_xticks(range(len(pillar_names)))
        ax.set_xticklabels([p.capitalize() for p in pillar_names], fontsize=10)
        ax.set_yticks(range(len(scenarios)))

        # Color y-labels by hedge outcome
        for i, s in enumerate(scenarios):
            color = 'black' if s["hedge"] else self.colors["hedge_fail"]
            weight = 'normal' if s["hedge"] else 'bold'
            suffix = "" if s["hedge"] else " [HEDGE FAILED]"
            ax.text(-0.5, i, f"{s['name']}{suffix}", ha='right', va='center',
                    fontsize=9, color=color, fontweight=weight)

        # Add cell values
        for i in range(len(scenarios)):
            for j in range(len(pillar_names)):
                value = data[i][j]
                color = 'white' if value < 0.3 or value > 0.7 else 'black'
                ax.text(j, i, f'{value:.2f}', ha='center', va='center',
                        color=color, fontsize=8)
                # Add breach marker
                if value < 0.2:
                    ax.add_patch(Rectangle((j-0.5, i-0.5), 1, 1,
                                           fill=False, edgecolor='red', linewidth=2))

        ax.set_title("MAC Pillar Scores Across 14 Crisis Events (1998-2025)\n"
                     "Red boxes indicate breaching pillars",
                     fontsize=13, fontweight='bold')

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('Pillar Score (0=Breach, 1=Ample)', fontsize=10)

        plt.tight_layout()

        if save:
            self._ensure_output_dir()
            filepath = os.path.join(self.output_dir, filename)
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"Saved: {filepath}")

        return fig


def plot_mac_vs_vix(output_dir: str = "figures") -> None:
    """Convenience function to generate MAC vs VIX comparison."""
    viz = CrisisVisualizer(output_dir)
    viz.plot_mac_vs_vix_conceptual()


def plot_pillar_breakdown(crisis_key: str, output_dir: str = "figures") -> None:
    """Convenience function to generate pillar breakdown for a specific crisis."""
    viz = CrisisVisualizer(output_dir)
    viz.plot_pillar_breakdown(crisis_key)


def plot_crisis_comparison(output_dir: str = "figures") -> None:
    """Convenience function to generate crisis comparison scatter plot."""
    viz = CrisisVisualizer(output_dir)
    viz.plot_crisis_comparison()


def generate_all_crisis_figures(output_dir: str = "figures") -> None:
    """
    Generate all crisis visualization figures.

    Args:
        output_dir: Directory to save figures
    """
    if not MATPLOTLIB_AVAILABLE:
        print("Error: matplotlib required. Install with: pip install matplotlib")
        return

    print("=" * 60)
    print("GENERATING MAC FRAMEWORK VISUALIZATIONS")
    print("=" * 60)
    print()

    viz = CrisisVisualizer(output_dir)

    # 1. MAC vs VIX conceptual comparison
    print("1. Generating MAC vs VIX conceptual diagram...")
    viz.plot_mac_vs_vix_conceptual()

    # 2. Crisis comparison scatter plot
    print("2. Generating crisis comparison scatter plot...")
    viz.plot_crisis_comparison()

    # 3. Positioning-hedge relationship
    print("3. Generating positioning-hedge relationship chart...")
    viz.plot_positioning_hedge_relationship()

    # 4. Heatmap of all crises
    print("4. Generating pillar heatmap...")
    viz.plot_mac_heatmap()

    # 5. Individual pillar breakdowns for key events
    key_events = [
        "lehman_2008",
        "covid_crash_2020",
        "repo_spike_2019",
        "april_tariffs_2025",
        "svb_crisis_2023",
        "volmageddon_2018",
    ]

    print("5. Generating pillar breakdowns for key events...")
    for key in key_events:
        if key in KNOWN_EVENTS:
            viz.plot_pillar_breakdown(key)

    print()
    print("=" * 60)
    print(f"All figures saved to: {output_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_crisis_figures()
