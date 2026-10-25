"""Render updated paper facts into the original MiroBench visual design."""
from __future__ import annotations

import json
import re
import struct
from html import escape
from pathlib import Path
from statistics import mean


def aggregate(data):
    families = data['families']
    order = data['metric_order']
    baseline = {
        f['name']: {
            measure: mean(ref[m[0]][measure] for ref in data['real_reference'].values() for m in f['metrics'])
            for measure in ['w1', 'cliffs']
        }
        for f in families
    }
    entries = []
    for method in ['ThreadPDG', 'OASIS', 'SynthPAI']:
        for model in ['gpt-5.4-mini', 'DeepSeek-V4.1-Flash', 'gpt-4o-mini']:
            rows = [r for r in data['results'] if r['method'] == method and r['model'] == model]
            values = {}
            for f in families:
                metrics = [r['metrics'][order.index(m[0])] for r in rows for m in f['metrics']]
                values[f['name']] = {measure: mean(m[measure] for m in metrics) for measure in ['w1', 'cliffs']}
            entries.append({'method': method, 'model': model, 'passes': sum(r['passes'] for r in rows), 'families': values})
    return baseline, sorted(entries, key=lambda r: -r['passes'])


def results_table(data):
    baseline, entries = aggregate(data)
    heads = ''.join(f'<th class="text-right">{f["name"]}</th>' for f in data['families'])
    bvalues = ''.join(f'<td class="text-right text-mute"><div>W₁ {baseline[f["name"]]["w1"]:.3f}</div><div class="text-[12px]">|δ| {baseline[f["name"]]["cliffs"]:.3f}</div></td>' for f in data['families'])
    rows = f'''<tr style="background:#F7F7F4;"><td class="text-mute2">—</td><td><div class="font-sans text-mute text-[12.5px]">Real reference</div><div class="font-mono text-[11px] text-mute2">150 vs. 150 · 200 repeats/domain</div></td>{bvalues}<td class="text-right text-mute2">—<div class="text-[11px]">sampling reference</div></td></tr>'''
    for i, row in enumerate(entries, 1):
        values = ''
        for f in data['families']:
            name = f['name']
            values += '<td class="text-right">'
            for key, label in [('w1', 'W₁'), ('cliffs', '|δ|')]:
                value = row['families'][name][key]
                values += f'<div{" class=text-mute" if key == "cliffs" else ""}>{label} {value:.3f} <span class="text-mute2 text-[11px]">×{value / baseline[name][key]:.1f}</span></div>'
            values += '</td>'
        rows += f'''<tr><td class="text-mute2">{i}</td><td><div class="font-sans text-[13px] {'text-accent font-medium' if row['method'] == 'ThreadPDG' else ''}">{row['method']}</div><div class="text-[11px] text-mute">{row['model']}</div></td>{values}<td class="text-right" style="border-left:1px solid #E4E4E0"><span class="{'text-accent font-medium' if row['method'] == 'ThreadPDG' else 'text-text'} text-[16px]">{row['passes']} / 96</span><div class="text-[11px] text-mute2">{row['passes']/96*100:.1f}%</div></td></tr>'''
    return f'''<section id="leaderboard" class="py-16 border-t border-line"><div class="max-w-[1280px] mx-auto px-6">
<div class="mb-7 reveal"><div class="sec-num">§ 02 — Results</div><h2 class="mt-2 text-[26px] lg:text-[30px] leading-[1.2] tracking-[-0.01em] font-medium max-w-[44ch]">How does <span class="serif-italic">ThreadPDG</span> compare with OASIS and SynthPAI?</h2></div>
<div class="reveal border border-line rounded-lg overflow-x-auto bg-white" tabindex="0" role="region" aria-label="Paper results by metric family"><table class="bench min-w-[1050px]"><caption class="sr-only">Nine method-model combinations across eight domains; family mean distances and both-test pass counts</caption><thead><tr><th style="width:46px">#</th><th style="width:200px">Method · Model</th>{heads}<th class="text-right" style="border-left:1px solid #E4E4E0;width:140px">Both p ≥ 0.05 ↑</th></tr></thead><tbody class="num">{rows}</tbody></table></div>
<div class="mt-5 text-[12.5px] text-mute leading-relaxed"><p>Family columns summarize mean Wasserstein distance W₁ and mean absolute Cliff’s delta across eight domains. Lower distances indicate closer distributions; ×N is the ratio to the repeated-real reference. W₁ means mix native metric scales and are descriptive summaries, not a scale-independent ranking.</p><p class="mt-2">All three methods are evaluated with the same twelve metrics across eight domains. A metric passes when <span class="mono-chip">p<sub>MWU</sub> ≥ 0.05</span> and <span class="mono-chip">p<sub>KS</sub> ≥ 0.05</span>. Totals count passing metric × domain cells out of <span class="num">12 × 8 = 96</span>. Each comparison uses 150 generated threads and 150 real test threads. Passing does not prove equivalence. <a class="ulink" href="https://arxiv.org/pdf/2606.14715">Paper §3.3, Table 3, Appendices C and K</a>.</p><p class="mt-2">Human evaluation: ThreadPDG is not distinguished in <span class="num">78.7%</span> of its non-tied discussion pairs, versus 61.1% for OASIS and 58.7% for SynthPAI. The study uses 436 retained annotators and 240 pairs across all three systems; generated-as-real and cannot-distinguish votes are combined by pair-level majority vote.</p></div>
<div class="mt-7 flex flex-wrap items-center justify-end gap-4"><a class="ulink text-[12px]" href="paper-results.csv" download>Download CSV</a><a class="ulink text-[12px]" href="paper-data.json" download>Full JSON</a><a href="results.html" class="group inline-flex items-center gap-2 px-4 py-2 border border-line2 rounded-md text-[13.5px] hover:border-text/40 hover:bg-surf transition-colors"><span>View full results</span><span class="font-mono text-mute2 text-[11px]">per-domain breakdown</span><span class="text-accent" aria-hidden="true">→</span></a></div></div></section>'''


def render(data, schema, bib):
    template = (Path(__file__).parent / 'templates' / 'home.html').read_text()
    affiliations = [1, 1, 2, 3, 2, 4, 1]
    authors = ['Yaoning Yu', 'Ye Yu', 'John Sciarappo', 'Haojing Luo', 'Kai-min Chang', 'Yi-Chia Wang', 'Haohan Wang']
    author_names = ' &nbsp;·&nbsp; '.join(f'<span class="text-text">{name}</span><sup>{aff}</sup>' for name, aff in zip(authors, affiliations))
    author_html = f'''<address class="mt-6 text-[14.5px] text-mute leading-relaxed not-italic">{author_names}<div class="mt-2 text-[13px] text-mute2"><sup>1</sup>University of Illinois Urbana–Champaign &nbsp; <sup>2</sup>U.S. Bank &nbsp; <sup>3</sup>Starc.Institute &nbsp; <sup>4</sup>Carnegie Mellon University</div></address>'''
    sb = {'name': 'ThreadBench', 'desc': 'ThreadBench compares generated and real Reddit discussions using 12 metrics across four families. Select a wedge for its definition.', 'children': [
        {'name': f['name'], 'desc': f['description'], 'children': [{'name': m[0], 'desc': m[2]} for m in f['metrics']]}
        for f in data['families']
    ]}
    colors = {'Uniformity': '#7C9CC9', 'Expression': '#7FA46D', 'Tone': '#E0A458', 'Interaction': '#A88AA8'}
    sbd = '// Original two-ring sunburst, updated to four families and twelve metrics.\nconst sbData = ' + json.dumps(sb, ensure_ascii=False) + ';\nconst familyColors = ' + json.dumps(colors) + ';'
    citation = f'''<section id="cite" class="py-16 border-t border-line"><div class="max-w-[1280px] mx-auto px-6"><div class="sec-num reveal">§ 05 — Citation</div><h2 class="reveal mt-2 text-[26px] lg:text-[30px] leading-[1.2] tracking-[-0.01em] font-medium">If you find <span class="serif-italic">ThreadBench</span> useful in your research, please cite our paper.</h2><p class="reveal mt-3 mb-7 text-[14.5px] text-mute leading-relaxed">Use the revised seven-author citation for <a class="ulink" href="https://arxiv.org/abs/2606.14715">arXiv:2606.14715</a>. <a class="ulink" href="threadbench.bib" download>Download BibTeX</a>.</p><div class="reveal code-block"><div class="code-bar"><span class="font-mono text-[11px] text-mute">threadbench.bib</span><button class="copy-btn" data-copy="{escape(bib, quote=True)}">copy</button></div><pre tabindex="0" aria-label="BibTeX citation">{escape(bib)}</pre></div></div></section>'''
    method = '''<div id="method" class="mt-12 reveal border-l-2 border-line2 pl-5"><h3 class="font-medium text-[15px]">How does ThreadPDG work?</h3><p class="mt-2 text-[14px] text-mute leading-[1.7]">The Planner reads a complete real seed discussion and plans branches and comment roles. The Writer generates new comments from these plans; up to K = 3 drafts are composed using separate reference-pool statistics. Drafts inherit the seed’s comment slots and reply topology. Independent root-post-only generation remains future work. <a class="ulink" href="method.html">Method details</a> · <a class="ulink" href="https://arxiv.org/pdf/2606.14715">Paper §4</a>.</p><p class="mt-3 text-[12px] text-mute2">Corpus: 9,817 threads · 8 domains · 116 reported subdomains. The per-domain counts in Table 1 sum to 117; we preserve the paper’s reported total and flag the discrepancy.</p></div>'''
    meta = '<meta name="robots" content="index,follow,max-image-preview:large">\n<meta name="citation_title" content="' + escape(data['title']) + '">\n' + ''.join(f'<meta name="citation_author" content="{a}">\n' for a in authors) + '<meta name="citation_pdf_url" content="https://arxiv.org/pdf/2606.14715">\n<meta name="citation_publication_date" content="2026">\n<meta name="citation_arxiv_id" content="2606.14715">\n<meta property="og:image" content="https://yyu6.github.io/ThreadBench/assets/social-card.png">\n<meta name="twitter:image" content="https://yyu6.github.io/ThreadBench/assets/social-card.png">'
    replacements = {'SCHEMA': json.dumps(schema, ensure_ascii=False), 'AUTHOR_NAMES': ', '.join(authors), 'AUTHORS': author_html, 'HOME_RESULTS': results_table(data), 'SUNBURST_DATA': sbd, 'CITATION': citation, 'METHOD_NOTE': method, 'EXTRA_META': meta}
    definitions = ''.join(f'<div class="mt-3"><h3 class="font-medium">{f["name"]}</h3><dl>' + ''.join(f'<dt class="mt-2 font-mono text-[11px]">{escape(m[0])}</dt><dd>{escape(m[2])}</dd>' for m in f['metrics']) + '</dl></div>' for f in data['families'])
    replacements['METRIC_DEFINITIONS'] = '<details id="metric-definitions" class="w-full text-[12px] text-mute leading-relaxed"><summary class="cursor-pointer text-accent">View all 12 metric definitions</summary>' + definitions + '</details>'
    for key, value in replacements.items():
        template = template.replace('@@' + key + '@@', value)
    if '@@' in template:
        raise ValueError('Unfilled home template token')
    def image_size(match):
        tag = match.group(0)
        path = re.search(r'src="([^"]+)"', tag)[1]
        png = (Path(__file__).resolve().parents[1] / 'docs' / path).read_bytes()
        width, height = struct.unpack('>II', png[16:24])
        return tag.replace('<img ', f'<img width="{width}" height="{height}" loading="lazy" ')
    return re.sub(r'<img src="figures/[^"]+\.png"[^>]*>', image_size, template)
