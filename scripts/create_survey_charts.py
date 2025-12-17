#!/usr/bin/env python3
"""
Argentina Penguin Survey - Static Visualization Charts

Creates publication-quality charts for reports:
1. Site comparison bar chart
2. Density distribution chart
3. Area vs count scatter plot
4. Summary dashboard

Usage:
    python scripts/create_survey_charts.py --output qc/panels/
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Style configuration
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'san_lorenzo': '#c41e3a',
    'caleta': '#2166ac',
    'caves': '#e31a1c',
    'plains': '#fd8d3c',
    'road': '#fecc5c',
    'box': '#91cf60',
    'island': '#4393c3',
}


def get_survey_data():
    """Return survey data for visualization."""
    return {
        'san_lorenzo': {
            'Caves': {'count': 908, 'area_ha': 0.60, 'density': 1518.4},
            'Plains': {'count': 453, 'area_ha': 0.98, 'density': 464.0},
            'Road': {'count': 359, 'area_ha': None, 'density': None},
            'Box - Caves': {'count': 32, 'area_ha': 1.15, 'density': 27.7},
            'Box - Bushes': {'count': 55, 'area_ha': 3.80, 'density': 14.5},
        },
        'caleta': {
            'Small Island': {'count': 1557, 'area_ha': 4.0, 'density': 389.2},
            'Tiny Island': {'count': 321, 'area_ha': 0.7, 'density': 458.6},
            'Box Count 1': {'count': 8, 'area_ha': None, 'density': None},
            'Box Count 2': {'count': 12, 'area_ha': None, 'density': None},
        }
    }


def create_site_comparison_chart(output_dir: Path):
    """Create bar chart comparing penguin counts by site."""
    data = get_survey_data()

    fig, ax = plt.subplots(figsize=(12, 7))

    # Prepare data
    sl_zones = list(data['san_lorenzo'].keys())
    sl_counts = [data['san_lorenzo'][z]['count'] for z in sl_zones]

    caleta_zones = list(data['caleta'].keys())
    caleta_counts = [data['caleta'][z]['count'] for z in caleta_zones]

    # Create grouped bar positions
    x_sl = np.arange(len(sl_zones))
    x_caleta = np.arange(len(caleta_zones)) + len(sl_zones) + 1

    # Plot bars
    bars_sl = ax.bar(x_sl, sl_counts, color=COLORS['san_lorenzo'], alpha=0.85,
                     edgecolor='white', linewidth=1.5, label='San Lorenzo')
    bars_caleta = ax.bar(x_caleta, caleta_counts, color=COLORS['caleta'], alpha=0.85,
                         edgecolor='white', linewidth=1.5, label='Caleta')

    # Add value labels on bars
    for bar, count in zip(bars_sl, sl_counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                f'{count}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    for bar, count in zip(bars_caleta, caleta_counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                f'{count}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Customize
    all_labels = sl_zones + [''] + caleta_zones
    ax.set_xticks(list(x_sl) + [len(sl_zones)] + list(x_caleta))
    ax.set_xticklabels(all_labels, rotation=30, ha='right', fontsize=10)

    ax.set_ylabel('Penguin Count', fontsize=12, fontweight='bold')
    ax.set_title('Argentina 2025 Penguin Survey - Counts by Zone', fontsize=14, fontweight='bold', pad=20)

    # Add totals
    sl_total = sum(sl_counts)
    caleta_total = sum(caleta_counts)

    ax.axhline(y=0, color='black', linewidth=0.5)

    # Summary text
    summary_text = f'San Lorenzo: {sl_total:,} | Caleta: {caleta_total:,} | Total: {sl_total + caleta_total:,}'
    ax.text(0.5, 0.98, summary_text, transform=ax.transAxes, ha='center', va='top',
            fontsize=12, fontweight='bold', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax.legend(loc='upper right', fontsize=11)
    ax.set_ylim(0, max(max(sl_counts), max(caleta_counts)) * 1.15)

    plt.tight_layout()
    output_path = output_dir / 'survey_counts_by_zone.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")


def create_density_chart(output_dir: Path):
    """Create horizontal bar chart of penguin densities."""
    data = get_survey_data()

    fig, ax = plt.subplots(figsize=(10, 8))

    # Collect zones with density data
    zones = []
    densities = []
    colors = []

    for zone, info in data['san_lorenzo'].items():
        if info['density']:
            zones.append(f"SL: {zone}")
            densities.append(info['density'])
            colors.append(COLORS['san_lorenzo'])

    for zone, info in data['caleta'].items():
        if info['density']:
            zones.append(f"CA: {zone}")
            densities.append(info['density'])
            colors.append(COLORS['caleta'])

    # Sort by density
    sorted_data = sorted(zip(zones, densities, colors), key=lambda x: x[1], reverse=True)
    zones, densities, colors = zip(*sorted_data)

    # Create horizontal bars
    y_pos = np.arange(len(zones))
    bars = ax.barh(y_pos, densities, color=colors, alpha=0.85, edgecolor='white', height=0.7)

    # Add value labels
    for bar, density in zip(bars, densities):
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
                f'{density:.0f}/ha', va='center', fontsize=10, fontweight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(zones, fontsize=11)
    ax.set_xlabel('Density (penguins/ha)', fontsize=12, fontweight='bold')
    ax.set_title('Penguin Density by Zone', fontsize=14, fontweight='bold', pad=15)

    # Add reference lines
    ax.axvline(x=100, color='gray', linestyle='--', alpha=0.5, label='100/ha')
    ax.axvline(x=500, color='gray', linestyle=':', alpha=0.5, label='500/ha')

    # Density category annotations
    ax.text(50, -0.8, 'Low', fontsize=9, color='green', ha='center')
    ax.text(300, -0.8, 'Medium', fontsize=9, color='orange', ha='center')
    ax.text(1000, -0.8, 'High', fontsize=9, color='red', ha='center')

    ax.set_xlim(0, max(densities) * 1.15)
    ax.invert_yaxis()

    # Legend
    sl_patch = mpatches.Patch(color=COLORS['san_lorenzo'], label='San Lorenzo')
    ca_patch = mpatches.Patch(color=COLORS['caleta'], label='Caleta')
    ax.legend(handles=[sl_patch, ca_patch], loc='lower right')

    plt.tight_layout()
    output_path = output_dir / 'survey_density_comparison.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")


def create_area_vs_count_scatter(output_dir: Path):
    """Create scatter plot of area vs count with density contours."""
    data = get_survey_data()

    fig, ax = plt.subplots(figsize=(10, 8))

    # Collect data points
    for site, zones in data.items():
        for zone, info in zones.items():
            if info['area_ha'] and info['count']:
                color = COLORS['san_lorenzo'] if site == 'san_lorenzo' else COLORS['caleta']
                marker = 'o' if 'Box' not in zone else 's'
                size = 100 + info['count'] / 5  # Size proportional to count

                ax.scatter(info['area_ha'], info['count'], c=color, s=size, alpha=0.7,
                          marker=marker, edgecolors='white', linewidths=1.5)

                # Label
                offset = (0.1, 20) if info['count'] > 500 else (0.05, 10)
                ax.annotate(zone, (info['area_ha'], info['count']),
                           xytext=(info['area_ha'] + offset[0], info['count'] + offset[1]),
                           fontsize=9, alpha=0.8)

    # Add density reference lines
    areas = np.linspace(0.1, 5, 100)
    for density, style, label in [(100, '--', '100/ha'), (500, '-.', '500/ha'), (1000, ':', '1000/ha')]:
        ax.plot(areas, areas * density, style, color='gray', alpha=0.5, label=label)

    ax.set_xlabel('Area (hectares)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Penguin Count', fontsize=12, fontweight='bold')
    ax.set_title('Area vs Count - Density Analysis', fontsize=14, fontweight='bold', pad=15)

    ax.set_xlim(0, 5)
    ax.set_ylim(0, 1800)

    # Legend
    sl_patch = mpatches.Patch(color=COLORS['san_lorenzo'], label='San Lorenzo')
    ca_patch = mpatches.Patch(color=COLORS['caleta'], label='Caleta')
    ax.legend(handles=[sl_patch, ca_patch], loc='upper left')

    plt.tight_layout()
    output_path = output_dir / 'survey_area_vs_count.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")


def create_summary_dashboard(output_dir: Path):
    """Create a comprehensive summary dashboard."""
    data = get_survey_data()

    fig = plt.figure(figsize=(16, 10))

    # Grid layout: 2x3
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)

    # ==========================================================================
    # Panel 1: Pie chart - Site distribution
    # ==========================================================================
    ax1 = fig.add_subplot(gs[0, 0])

    sl_total = sum(info['count'] for info in data['san_lorenzo'].values())
    caleta_total = sum(info['count'] for info in data['caleta'].values())

    sizes = [sl_total, caleta_total]
    labels = [f'San Lorenzo\n{sl_total:,}', f'Caleta\n{caleta_total:,}']
    colors_pie = [COLORS['san_lorenzo'], COLORS['caleta']]
    explode = (0.02, 0.02)

    ax1.pie(sizes, labels=labels, colors=colors_pie, explode=explode,
            autopct='%1.1f%%', startangle=90, textprops={'fontsize': 10})
    ax1.set_title('Distribution by Site', fontsize=12, fontweight='bold')

    # ==========================================================================
    # Panel 2: Stacked bar - Zone breakdown
    # ==========================================================================
    ax2 = fig.add_subplot(gs[0, 1])

    categories = ['San Lorenzo', 'Caleta']

    # San Lorenzo breakdown
    sl_caves = data['san_lorenzo']['Caves']['count']
    sl_plains = data['san_lorenzo']['Plains']['count']
    sl_road = data['san_lorenzo']['Road']['count']
    sl_box = data['san_lorenzo']['Box - Caves']['count'] + data['san_lorenzo']['Box - Bushes']['count']

    # Caleta breakdown
    ca_islands = data['caleta']['Small Island']['count'] + data['caleta']['Tiny Island']['count']
    ca_box = data['caleta']['Box Count 1']['count'] + data['caleta']['Box Count 2']['count']

    bar_width = 0.5
    x = np.arange(len(categories))

    # San Lorenzo stacked
    ax2.bar(0, sl_caves, bar_width, label='Caves', color='#e31a1c')
    ax2.bar(0, sl_plains, bar_width, bottom=sl_caves, label='Plains', color='#fd8d3c')
    ax2.bar(0, sl_road, bar_width, bottom=sl_caves+sl_plains, label='Road', color='#fecc5c')
    ax2.bar(0, sl_box, bar_width, bottom=sl_caves+sl_plains+sl_road, label='Box Counts', color='#91cf60')

    # Caleta stacked
    ax2.bar(1, ca_islands, bar_width, label='Islands', color='#4393c3')
    ax2.bar(1, ca_box, bar_width, bottom=ca_islands, label='Box Counts', color='#92c5de')

    ax2.set_xticks(x)
    ax2.set_xticklabels(categories)
    ax2.set_ylabel('Penguin Count')
    ax2.set_title('Zone Breakdown', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)

    # ==========================================================================
    # Panel 3: Density histogram
    # ==========================================================================
    ax3 = fig.add_subplot(gs[0, 2])

    densities = []
    for site, zones in data.items():
        for zone, info in zones.items():
            if info['density']:
                densities.append(info['density'])

    ax3.hist(densities, bins=10, color='steelblue', edgecolor='white', alpha=0.8)
    ax3.axvline(x=np.median(densities), color='red', linestyle='--', label=f'Median: {np.median(densities):.0f}/ha')
    ax3.set_xlabel('Density (penguins/ha)')
    ax3.set_ylabel('Frequency')
    ax3.set_title('Density Distribution', fontsize=12, fontweight='bold')
    ax3.legend()

    # ==========================================================================
    # Panel 4: Summary statistics table
    # ==========================================================================
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.axis('off')

    table_data = [
        ['Metric', 'San Lorenzo', 'Caleta', 'Total'],
        ['Total Count', f'{sl_total:,}', f'{caleta_total:,}', f'{sl_total + caleta_total:,}'],
        ['Zones Counted', '5', '4', '9'],
        ['Max Density', '1,518/ha', '459/ha', '1,518/ha'],
        ['Min Density', '15/ha', '389/ha', '15/ha'],
    ]

    table = ax4.table(cellText=table_data, loc='center', cellLoc='center',
                     colWidths=[0.3, 0.23, 0.23, 0.23])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5)

    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#404040')
        table[(0, i)].set_text_props(color='white', fontweight='bold')

    ax4.set_title('Summary Statistics', fontsize=12, fontweight='bold', y=0.95)

    # ==========================================================================
    # Panel 5: Key findings text
    # ==========================================================================
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.axis('off')

    findings = """
KEY FINDINGS

1. Total Count: 3,705 penguins
   - 2.4x larger than legacy dataset

2. Density Variation: 100x range
   - High: 1,518/ha (Caves)
   - Low: 15/ha (Box - Bushes)

3. Largest Populations:
   - Small Island: 1,557 (42%)
   - Caves: 908 (24%)

4. Detection Implications:
   - Need adaptive thresholds
   - Site-specific tuning required
"""

    ax5.text(0.1, 0.9, findings, transform=ax5.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # ==========================================================================
    # Panel 6: Comparison to legacy
    # ==========================================================================
    ax6 = fig.add_subplot(gs[1, 2])

    legacy_count = 1533
    new_count = sl_total + caleta_total

    bars = ax6.bar(['Legacy\n(Punta Tombo)', 'Argentina 2025'], [legacy_count, new_count],
                   color=['gray', 'forestgreen'], edgecolor='white', linewidth=2)

    # Add count labels
    for bar, count in zip(bars, [legacy_count, new_count]):
        ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                f'{count:,}', ha='center', fontsize=12, fontweight='bold')

    ax6.set_ylabel('Penguin Count')
    ax6.set_title('Legacy vs New Data', fontsize=12, fontweight='bold')
    ax6.set_ylim(0, new_count * 1.15)

    # Percent increase annotation
    pct_increase = (new_count - legacy_count) / legacy_count * 100
    ax6.annotate(f'+{pct_increase:.0f}%', xy=(1, new_count), xytext=(1.3, new_count * 0.8),
                fontsize=14, fontweight='bold', color='forestgreen',
                arrowprops=dict(arrowstyle='->', color='forestgreen'))

    # ==========================================================================
    # Overall title
    # ==========================================================================
    fig.suptitle('Argentina Penguin Survey 2025 - Summary Dashboard',
                 fontsize=16, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    output_path = output_dir / 'survey_dashboard.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Create survey visualization charts")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("qc/panels"),
        help="Output directory for charts"
    )

    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    print("Creating survey visualization charts...")
    print("=" * 50)

    create_site_comparison_chart(args.output)
    create_density_chart(args.output)
    create_area_vs_count_scatter(args.output)
    create_summary_dashboard(args.output)

    print("=" * 50)
    print(f"All charts saved to: {args.output}/")


if __name__ == "__main__":
    main()
