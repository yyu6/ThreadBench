#!/usr/bin/env python3
"""Refresh the original heatmap, polygon radars and ratio dotplot with paper data.

Requires numpy and matplotlib for authoring only. Uses transcribed paper values
in docs/paper-data.json; never uses the older five-domain corpus as new data.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MplPath
from matplotlib.patches import RegularPolygon
from matplotlib.projections import register_projection
from matplotlib.projections.polar import PolarAxes
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D

from paper_home import aggregate

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'docs/paper-data.json').read_text())
OUT = ROOT / 'docs/figures'
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'savefig.facecolor': 'white'})
DOMAINS = [d['name'] for d in DATA['domains']]
FAMILIES = DATA['families']


def heatmap():
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), sharey=True, layout='constrained')
    for ax, key, title in zip(axes, ['mwu_pass_rate', 'ks_pass_rate'], ['Mann–Whitney U', 'Kolmogorov–Smirnov']):
        matrix = np.array([[DATA['real_reference'][d][metric][key] for d in DOMAINS] for metric in DATA['metric_order']])
        im = ax.imshow(matrix, cmap='Blues', vmin=89, vmax=100, aspect='auto')
        ax.set_xticks(range(8), DOMAINS, rotation=40, ha='right')
        ax.set_yticks(range(12), ['Self-BLEU-4', 'Self-BERTScore', 'Semantic cosine', 'Average depth', 'Structural virality', 'Length CV', 'Story probability', 'Emotion entropy', 'Polite rate', 'Neutral rate', 'Impolite rate', 'Hard disagreement'])
        ax.set_title(title + ' · p ≥ 0.05', pad=14)
        ax.set_xticks(np.arange(-.5, 8, 1), minor=True)
        ax.set_yticks(np.arange(-.5, 12, 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=1.2)
        ax.tick_params(which='minor', bottom=False, left=False)
        for (i, j), value in np.ndenumerate(matrix):
            ax.text(j, i, f'{value:.1f}', ha='center', va='center', color='white' if value >= 96 else '#1a1a1a', fontsize=9)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.colorbar(im, ax=axes, shrink=.75, pad=.025, label='% of 200 repeated comparisons')
    fig.savefig(OUT/'realref_pvalue_heatmap.png', dpi=190)
    plt.close(fig)


def radar_projection(n):
    theta = np.linspace(0, 2*np.pi, n, endpoint=False)

    class RadarTransform(PolarAxes.PolarTransform):
        def transform_path_non_affine(self, path):
            if path._interpolation_steps > 1:
                path = path.interpolated(n)
            return MplPath(self.transform(path.vertices), path.codes)

    class RadarAxes(PolarAxes):
        name = 'threadbench_radar'
        PolarTransform = RadarTransform

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_theta_zero_location('N')

        def _gen_axes_patch(self):
            return RegularPolygon((.5, .5), n, radius=.5, edgecolor='black')

        def _gen_axes_spines(self):
            spine = Spine(axes=self, spine_type='circle', path=MplPath.unit_regular_polygon(n))
            spine.set_transform(Affine2D().scale(.5).translate(.5, .5) + self.transAxes)
            return {'polar': spine}

    register_projection(RadarAxes)
    return theta


def radar(key, output):
    theta = radar_projection(4)
    fig, ax = plt.subplots(figsize=(8.5, 8.2), subplot_kw={'projection': 'threadbench_radar'})
    names = [f['name'] for f in FAMILIES]
    values = np.array([[mean(DATA['real_reference'][d][m[0]][key] for m in f['metrics']) for f in FAMILIES] for d in DOMAINS])
    # Plot log10 manually to retain the polygon frame and equally spaced log rings.
    if key == 'w1':
        ticks = [.005, .01, .02, .05, .1, .2]
        low, high = np.log10(.004), np.log10(.22)
    else:
        ticks = [.02, .04, .06, .08]
        low, high = 0, .085
    ax.set_ylim(low, high)
    ax.set_yticks(np.log10(ticks) if key == 'w1' else ticks, [f'{v:g}' for v in ticks], color='#666', fontsize=9)
    ax.set_xticks(theta, names, fontsize=13)
    ax.tick_params(axis='x', pad=15)
    ax.grid(color='#ccc', linewidth=.8)
    colors = ['#4c78a8', '#f28e2b', '#59a14f', '#e15759', '#af7aa1', '#76b7b2', '#edc948', '#9c755f']
    closed = np.r_[theta, theta[0]]
    for domain, values_row, color in zip(DOMAINS, values, colors):
        y = np.log10(values_row) if key == 'w1' else values_row
        y = np.r_[y, y[0]]
        ax.plot(closed, y, color=color, linewidth=1.6, marker='o', markersize=3, label=domain)
        ax.fill(closed, y, color=color, alpha=.035)
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.11), ncol=4, frameon=False, fontsize=9, columnspacing=1)
    fig.subplots_adjust(top=.91, bottom=.17, left=.14, right=.86)
    fig.savefig(OUT/output, dpi=190, bbox_inches='tight')
    plt.close(fig)


def dotplot():
    baseline, entries = aggregate(DATA)
    entries = list(reversed(entries))
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), sharey=True)
    colors = ['#357c9d', '#b8aa90', '#b72c2c', '#453229']
    markers = ['o', 's', '^', 'D']
    for ax, measure, title in zip(axes, ['w1', 'cliffs'], [r'$W_1$ ratio', r'$|\delta_{Cliff}|$ ratio']):
        for j, (family, color, marker) in enumerate(zip(FAMILIES, colors, markers)):
            ratios = [r['families'][family['name']][measure] / baseline[family['name']][measure] for r in entries]
            ys = np.arange(len(entries)) + (j-1.5)*.17
            ax.scatter(ratios, ys, c=color, marker=marker, s=38, label=family['name'], zorder=3)
            for x, y in zip(ratios, ys):
                ax.annotate(f'{x:.1f}', (x, y), xytext=(6, 0), textcoords='offset points', va='center', fontsize=7)
        ax.axvline(1, linestyle='--', color='#596273', linewidth=1.1, label='Real-vs-real reference')
        ax.set_xscale('log')
        ax.set_xlim(.25, 28)
        ax.set_xticks([.3, .5, 1, 2, 5, 10, 20], ['0.3','0.5','1','2','5','10','20'])
        ax.grid(axis='x', color='#e1e3e7')
        ax.set_title(title, fontsize=16, fontweight='bold')
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#dce0e5')
    axes[0].set_yticks(range(len(entries)), [r['method']+'\n'+r['model'] for r in entries], fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=5, frameon=False, fontsize=10)
    fig.subplots_adjust(left=.16, right=.98, bottom=.09, top=.94, wspace=.05)
    fig.savefig(OUT/'realref_model_gap_dotplot.png', dpi=190)
    plt.close(fig)


if __name__ == '__main__':
    heatmap()
    radar('w1', 'realref_w1_radar.png')
    radar('cliffs', 'realref_cliff_radar.png')
    dotplot()
    print('Updated the four original figure types from revised paper data.')
