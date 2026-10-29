#!/usr/bin/env python3
"""Build the static paper site from paper-data.json; no runtime dependencies.

The legacy leaderboard pipeline remains separate: its corpus and pass rule are
different. Run with --check in CI to verify the committed paper pages/exports.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import struct
import sys
from datetime import date
from html import escape as e, unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from paper_home import render as render_home  # noqa: E402

DOCS = ROOT / "docs"
DATA = json.loads((DOCS / "paper-data.json").read_text())
BASE = "https://yyu6.github.io/ThreadBench/"
PAPER = "https://arxiv.org/abs/2606.14715"
PDF = "https://arxiv.org/pdf/2606.14715"
CODE = "https://github.com/yyu6/ThreadBench"
AUTHORS = ["Yaoning Yu", "Ye Yu", "John Sciarappo", "Haojing Luo", "Kai-min Chang", "Yi-Chia Wang", "Haohan Wang"]
BIB = """@article{yu2026threadbench,
  title = {ThreadBench: Benchmarking Realism in Agentic Simulation of Real-world Discussions},
  author = {Yu, Yaoning and Yu, Ye and Sciarappo, John and Luo, Haojing and Chang, Kai-min and Wang, Yi-Chia and Wang, Haohan},
  journal = {arXiv preprint arXiv:2606.14715},
  year = {2026},
  eprint = {2606.14715},
  archivePrefix = {arXiv},
  primaryClass = {cs.MA},
  doi = {10.48550/arXiv.2606.14715},
  url = {https://arxiv.org/abs/2606.14715}
}
"""
METRICS = {m[0]: (f["name"], m[1], m[2]) for f in DATA["families"] for m in f["metrics"]}
INSTITUTIONS = ["University of Illinois Urbana–Champaign", "U.S. Bank", "Starc.Institute", "Carnegie Mellon University"]
AFFILIATIONS = [0, 0, 1, 2, 1, 3, 0]  # index into INSTITUTIONS, in AUTHORS order
PERSON_URLS = {"Yaoning Yu": "https://yyu6.github.io/"}
DOI = "10.48550/arXiv.2606.14715"
SOCIAL = BASE + "assets/social-card.png"
SOCIAL_ALT = "ThreadBench: 9,817 real Reddit threads, 8 domains, 12 metrics in 4 families"
KEYWORDS = ["ThreadBench", "Reddit discussion simulation", "LLM social simulation evaluation", "social media simulation",
            "agent-based social simulation", "conversation simulation", "LLM agents", "multi-agent systems",
            "ThreadPDG", "OASIS", "SynthPAI"]
HOME_TITLE = "ThreadBench — Reddit Discussion Simulation Benchmark"
HOME_DESCRIPTION = "ThreadBench benchmarks LLM social simulation realism with 9,817 real Reddit threads, 8 domains and 12 metrics. Compare ThreadPDG, OASIS and SynthPAI results."
# Captions describe the existing homepage figures for structured data only; the images are unchanged.
FIGURES = {
    "realref_pvalue_heatmap.png": "Repeated real-vs-real MWU and KS p-value pass rates across ThreadBench's eight domains and twelve metrics",
    "realref_w1_radar.png": "Real-vs-real Wasserstein-1 distance by metric family and domain (log scale)",
    "realref_cliff_radar.png": "Real-vs-real absolute Cliff's delta by metric family and domain",
    "realref_model_gap_dotplot.png": "Per-model W1 and |Cliff's delta| ratios over the real-vs-real baseline, by metric family",
}
MODELS = ["gpt-5.4-mini", "DeepSeek-V4.1-Flash", "gpt-4o-mini"]
BASELINES = ["OASIS", "SynthPAI"]
HUMAN = {r["method"]: r["not_distinguished"] for r in DATA["human_evaluation"]["results"]}


def source(section: str, label: str | None = None) -> str:
    return f'<a class="source" href="{PDF}">{e(label or "Paper · " + section)} ↗</a>'


def passes(method: str, model: str) -> int:
    """Metric × domain cells (out of 96) passing both tests."""
    return sum(r["passes"] for r in DATA["results"] if r["method"] == method and r["model"] == model)


def plain(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html))


def human_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def home_faq() -> list[tuple[str, str]]:
    he = DATA["human_evaluation"]
    families = "; ".join(f'{f["name"]} ({", ".join(m[1] for m in f["metrics"])})' for f in DATA["families"])
    def best(method: str) -> str:
        model = max(MODELS, key=lambda m: passes(method, m))
        return f"{passes(method, model)} of 96 ({method} with {model})"
    return [
        ("What is ThreadBench?",
         f'ThreadBench is a benchmark for measuring realism in LLM-based social simulation of Reddit discussions, introduced in “{e(DATA["title"])}” (<a class="ulink" href="{PAPER}">arXiv:2606.14715</a>, v2, October 10, 2026). It contains 9,817 real Reddit threads across 8 domains ({", ".join(d["name"] for d in DATA["domains"])}) and 116 reported subdomains, and tests whether a set of generated threads reproduces the distributions of held-out real threads.'),
        ("What does ThreadBench measure?",
         f'ThreadBench scores 12 thread-level metrics in four families: {families}. Together they cover repeated wording and meaning, personal stories and emotion, politeness and disagreement, and the shape of the reply tree. <a class="ulink" href="#metric-definitions">Read all 12 definitions</a>.'),
        ("How does ThreadBench decide whether simulated discussions are realistic?",
         'For each method, model and domain, ThreadBench compares 150 generated threads with 150 held-out real test threads. A metric passes only when both two-sided Mann–Whitney U and Kolmogorov–Smirnov tests give p ≥ 0.05, so each system is scored on 12 × 8 = 96 metric–domain cells. Wasserstein-1 distance and absolute Cliff’s delta describe how large the remaining gaps are. Repeated real-vs-real samples pass both tests in 94.30% of comparisons. A pass means no difference was detected, not proof of equivalence.'),
        ("How do ThreadPDG, OASIS and SynthPAI compare on ThreadBench?",
         f'Under the same protocol, ThreadPDG passes {passes("ThreadPDG", "gpt-5.4-mini")} of 96 metric–domain cells with GPT-5.4-mini, {passes("ThreadPDG", "DeepSeek-V4.1-Flash")} with DeepSeek-V4.1-Flash and {passes("ThreadPDG", "gpt-4o-mini")} with GPT-4o-mini. The strongest baselines pass {best("OASIS")} and {best("SynthPAI")}. In the human study ({he["annotators"]} retained annotators, {he["pairs"]} matched pairs), ThreadPDG is not distinguished from real discussions in {HUMAN["ThreadPDG"]}% of its non-tied pairs, versus {HUMAN["OASIS"]}% for OASIS and {HUMAN["SynthPAI"]}% for SynthPAI. <a class="ulink" href="results.html">See all 72 comparisons</a>.'),
        ("What is ThreadPDG?",
         'ThreadPDG (Thread-Prompt-based Discussion Generation) is the paper’s prompt-based Planner–Writer method. The Planner reads a complete real seed thread and plans each branch and comment role; the Writer fills those plans with assigned personas; up to K = 3 drafts are combined branch by branch against reference-pool metric targets. It depends on real seed discussions, and root-post-only generation is future work. <a class="ulink" href="method.html">How ThreadPDG works</a>.'),
        ("When should I use ThreadBench?",
         'Use ThreadBench to check whether an LLM agent or social simulator produces multi-party discussions whose content and reply structure match real Reddit threads, rather than individual replies that merely sound fluent. It covers Reddit across eight domains. It does not score single-persona accuracy, other platforms, or group-level phenomena such as polarization or information cascades.'),
        ("How is ThreadBench different from OASIS, SynthPAI and SimBench?",
         'ThreadBench is an evaluation benchmark: it tests whether the distribution of generated discussions matches real Reddit threads. <a class="ulink" href="https://docs.oasis.camel-ai.org/introduction">OASIS</a> (CAMEL-AI) is a social media simulation framework, and <a class="ulink" href="https://github.com/eth-sri/SynthPAI">SynthPAI</a> is a synthetic Reddit-comment dataset for personal attribute inference; ThreadBench evaluates their generation methods as baselines. <a class="ulink" href="https://arxiv.org/abs/2510.17516">SimBench</a> benchmarks human-behavior simulation on structured tasks such as moral and economic choices; it is related work with a different scope and no shared score scale.'),
        ("What changed from MiroBench to ThreadBench?",
         'ThreadBench is the revised name and protocol of the earlier MiroBench project. The earlier MiroBench release, which is the Python code and data in the GitHub repository, covers 5 product domains and an archived 16-metric, MWU-only leaderboard. The revised paper uses 9,817 threads across 8 domains, 12 metrics, both MWU and KS tests, and introduces ThreadPDG. The expanded corpus and ThreadPDG implementation are not implied to be released in the repository.'),
        ("Where can I find the ThreadBench paper, results and data?",
         f'The paper is on <a class="ulink" href="{PAPER}">arXiv (2606.14715)</a>. Published results for all 72 comparisons and 864 metric-level p-value pairs are available as <a class="ulink" href="paper-results.csv">CSV</a> and <a class="ulink" href="paper-data.json">JSON</a>, and the <a class="ulink" href="results.html">results explorer</a> filters them by model, method and domain. The <a class="ulink" href="{CODE}">GitHub repository</a> holds the earlier MiroBench code and five-domain data. Plain-text summaries for AI assistants are at <a class="ulink" href="llms.txt">llms.txt</a> and <a class="ulink" href="llms-full.txt">llms-full.txt</a>.'),
        ("How do I cite ThreadBench?",
         f'Cite Yu et al. (2026), “{e(DATA["title"])},” arXiv:2606.14715, doi:{DOI}. Copy the <a class="ulink" href="#cite">BibTeX entry below</a> or download <a class="ulink" href="threadbench.bib">threadbench.bib</a>.'),
    ]


def method_faq() -> list[tuple[str, str]]:
    return [
        ("How does ThreadBench relate to other social simulation projects?",
         'ThreadBench evaluates the distributions of generated Reddit discussions against real threads. <a href="https://docs.oasis.camel-ai.org/introduction">OASIS</a> is a social media simulation framework; <a href="https://github.com/eth-sri/SynthPAI">SynthPAI</a> provides synthetic Reddit comments for personal attribute inference. Their generation methods are evaluated alongside ThreadPDG in this paper. <a href="https://arxiv.org/abs/2510.17516">SimBench</a> benchmarks human-behavior simulation across structured tasks such as moral and economic choices; it is related work, with a different evaluation scope and no shared score scale.'),
        ("Does ThreadPDG fine-tune the language model?",
         'No. ThreadPDG is prompt-based generation: the Planner and Writer are prompted with the seed thread, a structural template, a domain profile and sampled personas. No model-weight update is implied.'),
        ("Can ThreadPDG generate a discussion from only a root post?",
         'Not in the paper’s main setting. ThreadPDG conditions on a complete real seed thread, including its comments and reply relationships, and each draft inherits the seed’s comment count and reply-tree topology. Independent root-post-only generation is future work.'),
    ]


def results_faq() -> list[tuple[str, str]]:
    ours = {m: passes("ThreadPDG", m) for m in MODELS}
    others = [passes(b, m) for b in BASELINES for m in MODELS]
    assert all(ours[m] > max(passes(b, m) for b in BASELINES) for m in MODELS), "ThreadPDG no longer leads every backbone"
    return [
        ("How should ThreadBench MWU and KS pass rates be interpreted?",
         'A metric passes when both two-sided Mann–Whitney U and Kolmogorov–Smirnov tests give p ≥ 0.05 against 150 held-out real threads. A pass means no difference was detected at that threshold; it is not proof of equivalence. The paper’s p-values are rounded, so use the published pass flags instead of recomputing decisions from a displayed “.05”. For reference, repeated real-vs-real samples pass both tests in 94.30% of metric comparisons.'),
        ("Which method performs best on ThreadBench?",
         f'ThreadPDG passes the most metric–domain cells with every backbone: {ours["gpt-5.4-mini"]}/96 with GPT-5.4-mini, {ours["DeepSeek-V4.1-Flash"]}/96 with DeepSeek-V4.1-Flash and {ours["gpt-4o-mini"]}/96 with GPT-4o-mini. The six OASIS and SynthPAI configurations pass between {min(others)}/96 and {max(others)}/96. Results still vary by domain, and politeness, disagreement and length remain challenges.'),
        ("What does “not distinguished” mean in the human evaluation?",
         f'A pair is “not distinguished” when votes selecting the generated thread as real, plus “cannot distinguish” votes, outnumber votes selecting the real thread. Ties are excluded. ThreadPDG reaches {HUMAN["ThreadPDG"]}%, versus {HUMAN["OASIS"]}% for OASIS and {HUMAN["SynthPAI"]}% for SynthPAI, across {DATA["human_evaluation"]["annotators"]} retained annotators and {DATA["human_evaluation"]["pairs"]} matched pairs.'),
    ]


def faq_html(items: list[tuple[str, str]]) -> str:
    return ''.join(f'<h3>{e(q)}</h3><p>{a}</p>' for q, a in items)


def person(i: int, name: str) -> dict:
    node = {"@type": "Person", "@id": BASE + "#author-" + name.lower().replace(" ", "-"), "name": name,
            "affiliation": {"@type": "Organization", "name": INSTITUTIONS[AFFILIATIONS[i]]}}
    if name in PERSON_URLS:
        node["url"] = PERSON_URLS[name]
    return node


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def schema(page: str, title: str, description: str, faq: list[tuple[str, str]] = ()) -> dict:
    url = BASE + page
    authors = [person(i, a) for i, a in enumerate(AUTHORS)]
    webpage = {"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": title,
               "description": description, "dateModified": DATA["updated"], "inLanguage": "en",
               "isPartOf": {"@id": BASE + "#website"}, "about": {"@id": BASE + "#paper"},
               "primaryImageOfPage": {"@type": "ImageObject", "contentUrl": SOCIAL, "width": 1200, "height": 630, "caption": SOCIAL_ALT}}
    if faq:
        webpage["@type"] = ["WebPage", "FAQPage"]
        webpage["mainEntity"] = [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in faq]
    graph = [
        {"@type": "WebSite", "@id": BASE + "#website", "name": "ThreadBench", "alternateName": "MiroBench", "url": BASE,
         "description": HOME_DESCRIPTION, "inLanguage": "en"},
        webpage,
        {"@type": "ScholarlyArticle", "@id": BASE + "#paper", "name": DATA["title"],
         "headline": DATA["title"], "author": authors,
         "url": PAPER, "sameAs": ["https://doi.org/" + DOI],
         "identifier": [{"@type": "PropertyValue", "propertyID": "arXiv", "value": "2606.14715"},
                        {"@type": "PropertyValue", "propertyID": "DOI", "value": DOI}],
         "version": DATA["paper_version"], "dateModified": DATA["paper_date"], "inLanguage": "en", "isAccessibleForFree": True,
         "publisher": {"@type": "Organization", "name": "arXiv", "url": "https://arxiv.org/"},
         "keywords": KEYWORDS, "image": SOCIAL,
         "description": "A Reddit discussion simulation benchmark with 9,817 real threads, 8 domains, 116 subdomains and 12 metrics in four families, with ThreadPDG Planner–Writer generation.",
         "mentions": [{"@type": "SoftwareApplication", "name": "OASIS", "alternateName": "Open Agent Social Interaction Simulations", "url": "https://github.com/camel-ai/oasis"},
                      {"@type": "Dataset", "name": "SynthPAI", "url": "https://github.com/eth-sri/SynthPAI"}],
         "encoding": {"@type": "MediaObject", "contentUrl": PDF, "encodingFormat": "application/pdf"}},
    ]
    if page in ("", "results.html"):
        graph.append({"@type": "Dataset", "@id": BASE + "#results-dataset", "name": "ThreadBench paper results",
                      "description": "Metric-level results from the ThreadBench paper: 72 comparisons (3 generation methods × 3 LLM backbones × 8 Reddit domains) and 864 rounded Mann–Whitney U and Kolmogorov–Smirnov p-value pairs with published pass decisions, Wasserstein-1 distances and absolute Cliff’s delta. Each comparison uses 150 generated and 150 held-out real threads from the 9,817-thread ThreadBench corpus. The export contains paper results, not raw Reddit corpus data.",
                      "url": BASE + "results.html", "creator": [{"@id": a["@id"]} for a in authors],
                      "isBasedOn": {"@id": BASE + "#paper"}, "citation": PAPER, "license": CODE + "/blob/main/LICENSE",
                      "keywords": KEYWORDS, "inLanguage": "en", "isAccessibleForFree": True, "dateModified": DATA["updated"],
                      "measurementTechnique": ["Two-sided Mann–Whitney U test", "Two-sided Kolmogorov–Smirnov test", "Wasserstein-1 distance", "Absolute Cliff's delta"],
                      "variableMeasured": [{"@type": "PropertyValue", "name": label, "propertyID": key, "description": f"{fam}: {desc}"} for key, (fam, label, desc) in METRICS.items()],
                      "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": BASE + "paper-results.csv"},
                                       {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE + "paper-data.json"}]})
    if not page:
        graph.append({"@type": "DefinedTermSet", "@id": BASE + "#metrics", "name": "ThreadBench metrics",
                      "description": "Twelve thread-level metrics in four families (Uniformity, Expression, Tone, Interaction) used to compare generated and real Reddit discussions.",
                      "hasDefinedTerm": [{"@type": "DefinedTerm", "name": label, "termCode": key, "description": f"{fam}: {desc}", "inDefinedTermSet": {"@id": BASE + "#metrics"}}
                                         for key, (fam, label, desc) in METRICS.items()]})
        graph.append({"@type": "SoftwareSourceCode", "@id": BASE + "#code", "name": "ThreadBench repository (earlier MiroBench implementation)",
                      "codeRepository": CODE, "programmingLanguage": "Python", "license": "https://opensource.org/licenses/MIT",
                      "description": "Python package and mirobench CLI for scoring generated discussion threads and comparing them with real Reddit threads. It documents the earlier MiroBench five-domain release, not the expanded ThreadBench corpus or the ThreadPDG implementation.",
                      "subjectOf": {"@id": BASE + "#paper"}})
        webpage["image"] = []
        for name, caption in FIGURES.items():
            width, height = png_size(DOCS / "figures" / name)
            webpage["image"].append({"@type": "ImageObject", "contentUrl": BASE + "figures/" + name, "caption": caption, "width": width, "height": height})
    if page:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ThreadBench", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": "Results" if page == "results.html" else "ThreadPDG", "item": url}]})
    return {"@context": "https://schema.org", "@graph": graph}


def head_meta() -> str:
    authors = ''.join(f'<meta name="citation_author" content="{e(a)}">\n<meta name="citation_author_institution" content="{e(INSTITUTIONS[i])}">\n'
                      for a, i in zip(AUTHORS, AFFILIATIONS))
    return f'''<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="text/plain" href="llms.txt" title="ThreadBench summary for AI assistants">
<meta property="og:site_name" content="ThreadBench">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{SOCIAL}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(SOCIAL_ALT)}">
<meta property="article:modified_time" content="{DATA['updated']}">
<meta name="twitter:image" content="{SOCIAL}">
<meta name="twitter:image:alt" content="{e(SOCIAL_ALT)}">
<meta name="citation_title" content="{e(DATA['title'])}">
{authors}<meta name="citation_publication_date" content="2026">
<meta name="citation_arxiv_id" content="2606.14715">
<meta name="citation_doi" content="{DOI}">
<meta name="citation_pdf_url" content="{PDF}">
<meta name="citation_abstract_html_url" content="{PAPER}">
<meta name="citation_keywords" content="{e('; '.join(KEYWORDS))}">'''


def layout(page: str, title: str, description: str, body: str, faq: list[tuple[str, str]]) -> str:
    def active(p: str) -> str:
        return ' aria-current="page"' if page == p else ""
    home_template = (ROOT / 'scripts/templates/home.html').read_text()
    old_header = home_template[home_template.index('<header id="nav"'):home_template.index('</header>') + len('</header>')]
    for anchor in ['top', 'motivation', 'leaderboard', 'realref', 'metrics', 'quickstart', 'faq', 'cite']:
        old_header = old_header.replace('href="#' + anchor + '"', 'href="./#' + anchor + '"')
    old_styles_start = home_template.index('<link rel="stylesheet" href="assets/original-fonts.css"')
    old_styles_end = home_template.index('</style>', old_styles_start) + len('</style>')
    old_styles = home_template[old_styles_start:old_styles_end]
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="author" content="{e(', '.join(AUTHORS))}">
<link rel="canonical" href="{BASE + page}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{BASE + page}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
{head_meta()}
<script type="application/ld+json">{json.dumps(schema(page, title, description, faq), ensure_ascii=False)}</script>
{old_styles}
<link rel="stylesheet" href="assets/site.css">
<script src="assets/site.js" defer></script>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
{old_header}
<main id="main">{body}</main>
<footer class="site-footer"><div class="container footer-grid"><div><a class="brand" href="./">ThreadBench.</a><p>Measuring the realism of online discussions.</p><p class="small">Previously MiroBench · Research preprint, 2026</p></div><nav aria-label="Resources"><a href="{PAPER}">arXiv paper ↗</a><a href="{CODE}">GitHub repository ↗</a><a href="paper-data.json">Paper results (JSON)</a><a href="threadbench.bib" download>BibTeX</a><a href="llms.txt">Site summary for agents</a><a href="llms-full.txt">Full text for agents</a></nav></div><div class="container footer-bottom"><span>Website updated <time datetime="{DATA['updated']}">{human_date(DATA['updated'])}</time></span><span>Paper v2 · <time datetime="2026-10-10">October 10, 2026</time></span></div></footer>
<div id="status" class="toast" role="status" aria-live="polite"></div>
</body></html>
'''


def method_steps() -> str:
    return '''<ol class="method-steps"><li><span class="step-number">01</span><span class="eyebrow">PLANNER</span><h3>Learn how a thread develops.</h3><p>Read a real seed thread. Plan each branch’s direction and each comment’s role within the reply template.</p></li><li><span class="step-number">02</span><span class="eyebrow">WRITER</span><h3>Turn plans into new comments.</h3><p>Use comment plans, assigned personas and prior generated context to fill the planned discussion.</p></li><li><span class="step-number">03</span><span class="eyebrow">COMPOSITION</span><h3>Combine the strongest branches.</h3><p>Generate multiple drafts and select branches against reference-pool metric targets for the current seed.</p></li></ol>'''


def citation() -> str:
    return f'''<section id="cite" class="section container" aria-labelledby="cite-title"><div class="section-label">CITATION</div><div class="section-heading"><div><h2 id="cite-title">Cite <em>ThreadBench.</em></h2><p>If the benchmark or method supports your research, please cite the paper.</p></div><a class="text-link" href="threadbench.bib" download>Download BibTeX ↓</a></div><div class="code-block"><div class="code-toolbar"><span>threadbench.bib</span><button class="copy-button" data-copy-target="citation-text">Copy BibTeX</button></div><pre id="citation-text" tabindex="0" aria-label="BibTeX citation">{e(BIB.rstrip())}</pre></div></section>'''


def method_page() -> str:
    return f'''<div class="container subpage-hero"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="./">ThreadBench</a><span aria-hidden="true">/</span><span>ThreadPDG</span></nav><p class="eyebrow">THE GENERATION METHOD</p><h1>Plan how a discussion grows.<br><em>Write what comes next.</em></h1><p class="page-deck">ThreadPDG—Thread-Prompt-based Discussion Generation—is a Planner–Writer framework that studies a complete real seed discussion, generates multiple drafts and combines their branches using thread-level statistics.</p><div class="hero-actions"><a class="button primary" href="{PDF}">Read §4 and Appendix F ↗</a><a class="button" href="results.html">See the evaluation →</a></div></div>
<section class="section tinted" aria-labelledby="workflow-title"><div class="container"><div class="section-label">01 / THE WORKFLOW</div><h2 id="workflow-title">From a real example<br><em>to a new discussion.</em></h2>{method_steps()}</div></section>
<section class="section container prose-grid" aria-labelledby="conditioning-title"><div><div class="section-label">02 / CONDITIONING</div><h2 id="conditioning-title">What goes into<br><em>generation?</em></h2></div><div class="prose"><h3>A complete real seed thread</h3><p>The Planner reads the root post, comments and parent–reply relationships. A structural template specifies comment slots, reply structure and length targets. Each draft inherits the seed’s comment count and reply-tree topology. The Planner determines the direction of each branch and what every comment should contribute.</p><h3>A domain profile and assigned personas</h3><p>A profile derived from the domain’s separate reference pool guides the discussion patterns. The Writer follows the plans and template, with personas sampled from MatrAIx and previously generated discussion context. This is prompt-based generation; no model-weight update is implied.</p><h3>A separate reference pool</h3><p>For branch composition, each seed receives a randomly sampled reference thread from the domain’s reference pool. That one thread supplies the targets for all metrics, preserving relationships among the target metric values. The selection objective uses metric weights and reference-pool interquartile ranges.</p>{source('§4, Appendix F')}</div></section>
<section class="section tinted" aria-labelledby="composition-title"><div class="container prose-grid"><div><div class="section-label">03 / MULTI-DRAFT COMPOSITION</div><h2 id="composition-title">Several drafts.<br><em>One composed thread.</em></h2></div><div class="prose"><p>The main experiments allow up to <strong>K = 3</strong> Planner–Writer drafts per seed. A branch contains a parent comment and all its sub-comments. The final thread can take different branches from different drafts of that same seed.</p><p>The search minimizes a weighted sum of squared, IQR-normalized differences between the composed thread’s metrics and its sampled reference targets. Selection uses the current seed’s drafts and target plus fixed reference-pool statistics, without other held-out test data.</p><aside class="note" aria-label="Evaluation separation"><strong>Keep the pools separate.</strong> Each domain has non-overlapping seed, reference and test pools. Reference-pool statistics guide generation and selection; an independently sampled group of 150 held-out real test threads is used for final evaluation.</aside>{source('§4.2, §5.1')}</div></div></section>
<section class="section container prose-grid" aria-labelledby="limitations-title"><div><div class="section-label">04 / SCOPE &amp; LIMITATIONS</div><h2 id="limitations-title">Progress with<br><em>a clear boundary.</em></h2></div><div class="prose"><p>ThreadPDG is a case study in using ThreadBench to improve discussion realism. It currently depends on corresponding real seed discussions. Generating equally realistic threads independently at inference time is future work.</p><p>Results vary by model and domain. With GPT-5.4-mini, the method passes 67–92% of metrics; with DeepSeek-V4.1-Flash, 58–100%; and with GPT-4o-mini, 17–42%. Politeness, disagreement and length remain challenges.</p><p>Passing statistical tests means a difference was not detected at the chosen threshold. It does not prove distributional equivalence or establish realism beyond the benchmark’s measured properties.</p>{source('§5, Appendix L')}{faq_html(method_faq())}<p>For the ThreadBench protocol’s direct comparisons, see <a href="results.html">ThreadPDG, OASIS and SynthPAI results</a>. For metric definitions, see the <a href="./#metric-definitions">twelve-metric reference</a>.</p><p><a class="button" href="results.html">Inspect all 72 comparisons →</a></p></div></section>'''


def results_page() -> str:
    def options(xs: list[str]) -> str:
        return ''.join(f'<option value="{e(x)}">{e(x)}</option>' for x in xs)
    summary = ''
    for model in ['gpt-5.4-mini', 'DeepSeek-V4.1-Flash', 'gpt-4o-mini']:
        for method in ['ThreadPDG', 'OASIS', 'SynthPAI']:
            rows = [r for r in DATA['results'] if r['model'] == model and r['method'] == method]
            counts = [r['passes'] for r in rows]
            summary += f'<tr><th scope="row">{model}</th><td>{method}</td><td>{min(counts)}/12–{max(counts)}/12</td><td>{round(min(counts)/12*100)}–{round(max(counts)/12*100)}%</td></tr>'
    comparisons = ''
    for r in DATA['results']:
        mrows = ''
        for key, m in zip(DATA['metric_order'], r['metrics']):
            fam, label, _ = METRICS[key]
            mrows += f'<tr><th scope="row">{label}<code>{key}</code></th><td>{fam}</td><td>{e(m["mwu"])}</td><td>{e(m["ks"])}</td><td><span class="metric-verdict {"pass" if m["pass"] else "fail"}">{"Pass" if m["pass"] else "Fail"}</span></td></tr>'
        comparisons += f'''<tr data-result-row data-domain="{e(r['domain'])}" data-method="{r['method']}" data-model="{r['model']}"><th scope="row">{r['domain']}</th><td><span class="method-name {'ours' if r['method'] == 'ThreadPDG' else ''}">{r['method']}</span></td><td class="model-cell">{r['model']}</td><td><div class="pass-cell"><span class="pass-track" aria-hidden="true"><i style="width:{r['passes']/12*100:.3f}%"></i></span><strong>{r['passes']}/12</strong><span>{round(r['passes']/12*100)}%</span></div></td><td><details class="metric-detail"><summary>12 metrics <span aria-hidden="true">＋</span></summary><div class="metric-popover"><h3>{r['method']} · {r['model']} · {r['domain']}</h3><table><caption>Published rounded p-values and pass decisions</caption><thead><tr><th scope="col">Metric</th><th scope="col">Family</th><th scope="col">MWU p</th><th scope="col">KS p</th><th scope="col">Decision</th></tr></thead><tbody>{mrows}</tbody></table></div></details></td></tr>'''
    human = ''.join(f'<tr><th scope="row">{r["method"]}</th><td>{r["not_distinguished"]}%</td><td>{100-r["not_distinguished"]:.1f}%</td></tr>' for r in DATA['human_evaluation']['results'])
    return f'''<div class="container subpage-hero"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="./">ThreadBench</a><span aria-hidden="true">/</span><span>Results</span></nav><p class="eyebrow">THE PAPER, IN NUMBERS</p><h1>A closer look at<br><em>discussion realism.</em></h1><p class="page-deck">Explore all 72 comparisons from ThreadBench: three methods, three models and eight domains. Each result reports how many of twelve metrics pass both statistical tests against held-out real discussions.</p><div class="hero-actions"><a class="button primary" href="paper-results.csv" download>Download results CSV ↓</a><a class="button" href="paper-data.json" download>Download full JSON ↓</a>{source('Table 3')}</div></div>
<section class="section tinted" aria-labelledby="ranges-title"><div class="container"><div class="section-label">01 / ACROSS EIGHT DOMAINS</div><h2 id="ranges-title">The model <em>matters.</em></h2><p>Domain-level ranges from the paper; higher is better for pass rates. ThreadPDG’s 58–100% headline covers the two stronger backbones. GPT-4o-mini reaches 17–42%.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable research table"><table class="range-table"><caption>Pass-rate ranges, by model and method</caption><thead><tr><th scope="col">Model</th><th scope="col">Method</th><th scope="col">Passing metrics</th><th scope="col">Pass-rate range</th></tr></thead><tbody>{summary}</tbody></table></div></div></section>
<section id="explorer" class="section container" aria-labelledby="explorer-title"><div class="section-label">02 / RESULT EXPLORER</div><div class="section-heading"><div><h2 id="explorer-title">Every domain.<br><em>Every comparison.</em></h2><p>150 generated threads and 150 real test threads per comparison. Open a row to inspect its twelve metrics.</p></div></div>
<form id="result-filters" class="filters" hidden><div><label for="model-filter">Model</label><select id="model-filter" name="model"><option value="">All models</option>{options(['gpt-5.4-mini','DeepSeek-V4.1-Flash','gpt-4o-mini'])}</select></div><div><label for="method-filter">Method</label><select id="method-filter" name="method"><option value="">All methods</option>{options(['ThreadPDG','OASIS','SynthPAI'])}</select></div><div><label for="domain-filter">Domain</label><select id="domain-filter" name="domain"><option value="">All domains</option>{options([d['name'] for d in DATA['domains']])}</select></div><button type="reset" class="reset-button">Reset filters</button><a class="text-link" id="share-results" href="results.html#explorer">Copy filtered link ↗</a></form>
<p id="result-count" class="result-count" role="status" aria-live="polite">72 comparisons · 12 metrics each</p><div class="table-wrap results-wrap" tabindex="0" role="region" aria-label="Scrollable comparison results"><table class="results-table"><caption class="sr-only">Metric pass counts and detailed p-values for every paper comparison</caption><thead><tr><th scope="col">Domain</th><th scope="col">Method</th><th scope="col">Model</th><th scope="col">Metrics passing both tests</th><th scope="col">Details</th></tr></thead><tbody>{comparisons}</tbody></table></div>
<aside class="note" aria-label="Interpreting p-values"><strong>Reading the numbers.</strong> The protocol uses p<sub>MWU</sub> ≥ 0.05 and p<sub>KS</sub> ≥ 0.05. Values in the paper table are rounded; a displayed “.05” can correspond to either decision. We preserve the paper’s bold/pass annotations and published counts rather than recomputing decisions from rounded values. A pass is not proof of equivalence. {source('§3.3, Table 3')}</aside>
<p class="small">These are transcribed paper results, not a live community ranking. <a href="leaderboard.html">Earlier MiroBench leaderboard (archived protocol)</a>.</p></section>
<section id="human" class="section tinted" aria-labelledby="human-title"><div class="container prose-grid"><div><div class="section-label">03 / HUMAN EVALUATION</div><h2 id="human-title">What people<br><em>could distinguish.</em></h2></div><div class="prose"><p>The study retains <strong>436 annotators</strong> and evaluates <strong>240 matched pairs</strong>: eight domains × three systems × ten pairs. Each pair presents a real discussion and a generated discussion for the same post.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable research table"><table><caption>Paper Table 2 · Pair-level majority outcomes</caption><thead><tr><th scope="col">Method</th><th scope="col">Not distinguished</th><th scope="col">Distinguished</th></tr></thead><tbody>{human}</tbody></table></div><p>A pair is “not distinguished” when votes selecting the generated thread as real, plus “cannot distinguish” votes, outnumber votes selecting the real thread. Ties are excluded. The 78.7% result is a proportion of ThreadPDG pairs with a majority outcome, not a proportion of all annotators.</p>{source('§5, Appendix I')}</div></div></section>
<section class="section container prose-grid" aria-labelledby="setup-title"><div><div class="section-label">04 / EVALUATION SETUP</div><h2 id="setup-title">Separate pools.<br><em>Shared protocol.</em></h2></div><div class="prose"><p>The real corpus is divided into non-overlapping seed, reference and test pools for each domain. All three methods use real seed discussions for generation. ThreadPDG additionally uses reference-pool information for profiles, targets and composition; its main draft budget is K = 3.</p><p>ThreadBench compares the generated and held-out real metric distributions with two-sided MWU and KS tests. The paper also reports Wasserstein-1 distance and absolute Cliff’s delta. In the repeated real-vs-real sanity check, both tests pass in 94.30% of metric comparisons.</p><p>Data provenance: the user-provided paper source, <code>sections/results-main-table.tex</code>, checked against arXiv v2. The JSON export retains rounded p-values, explicit pass flags, metric ordering and source metadata.</p>{source('§3.3, §5.1')}<p><a class="text-link" href="method.html">Understand ThreadPDG’s conditioning →</a></p></div></section>
<section id="faq" class="section tinted" aria-labelledby="faq-title"><div class="container prose-grid"><div><div class="section-label">05 / QUESTIONS</div><h2 id="faq-title">Reading the results<br><em>correctly.</em></h2></div><div class="prose">{faq_html(results_faq())}{source('§3.3, §5, Table 3')}</div></div></section>'''


def llms_full() -> str:
    """Long-form Markdown for AI assistants (llms.txt convention); generated so its numbers stay in sync."""
    he = DATA["human_evaluation"]
    out = ["# ThreadBench", "", "> " + plain(home_faq()[0][1]), "",
           f"- Canonical site: {BASE}", f"- Paper: {PAPER} (PDF {PDF}; DOI https://doi.org/{DOI})",
           f"- Repository: {CODE} (earlier MiroBench implementation and five-domain data; not the expanded corpus or ThreadPDG)",
           f"- Paper version: {DATA['paper_version']}, {human_date(DATA['paper_date'])}. Website updated {human_date(DATA['updated'])}.",
           "", "## Corpus", "", "| Domain | Real threads | Subdomains |", "|---|---:|---:|"]
    out += [f"| {d['name']} | {d['threads']:,} | {d['subdomains']} |" for d in DATA["domains"]]
    out += [f"| Total | {sum(d['threads'] for d in DATA['domains']):,} | {DATA['reported_total_subdomains']} (reported) |", "",
            DATA["source"]["inventory_note"], "", "Each domain has non-overlapping seed, reference and test pools.", "", "## Metrics", ""]
    for f in DATA["families"]:
        out += [f"### {f['name']}: {f['question']}", "", f["description"], ""]
        out += [f"- {m[1]} (`{m[0]}`): {m[2]}" for m in f["metrics"]] + [""]
    out += ["## Results", "", "Metric–domain cells passing both MWU and KS tests (p ≥ 0.05), out of 12 metrics × 8 domains = 96. Each comparison uses 150 generated and 150 held-out real threads.", "",
            "| Method | Model | Passing cells | Share | Per-domain range (of 12) |", "|---|---|---:|---:|---:|"]
    for method in ["ThreadPDG", *BASELINES]:
        for model in MODELS:
            counts = [r["passes"] for r in DATA["results"] if r["method"] == method and r["model"] == model]
            out.append(f"| {method} | {model} | {passes(method, model)}/96 | {passes(method, model) / 96 * 100:.1f}% | {min(counts)}–{max(counts)} |")
    out += ["", "### Per-domain pass counts", "", "| Domain | Method | Model | Metrics passing (of 12) |", "|---|---|---|---:|"]
    out += [f"| {r['domain']} | {r['method']} | {r['model']} | {r['passes']} |" for r in DATA["results"]]
    out += ["", "Repeated real-vs-real reference (150 vs 150 real threads, 200 repeats per domain): MWU passes 94.99%, KS 96.95% and both 94.30% of metric comparisons.", "",
            "## Human evaluation", "", f"{he['annotators']} retained annotators; {he['pairs']} matched pairs (8 domains × 3 systems × 10 pairs). {he['aggregation']}", "",
            "| Method | Not distinguished |", "|---|---:|"]
    out += [f"| {r['method']} | {r['not_distinguished']}% |" for r in he["results"]]
    out += ["", "## Frequently asked questions", ""]
    for q, a in home_faq() + method_faq() + results_faq():
        out += [f"### {q}", "", plain(a), ""]
    out += ["## Data downloads", "", f"- [Paper result CSV]({BASE}paper-results.csv): one row per comparison and metric (864 rows).",
            f"- [Paper result JSON]({BASE}paper-data.json): 72 comparisons with rounded p-values, explicit pass flags, W1, Cliff's delta and source metadata.",
            f"- [BibTeX]({BASE}threadbench.bib)", "", "## Citation", "", "```bibtex", BIB.rstrip(), "```", ""]
    return "\n".join(out)


def sitemap() -> str:
    images = ''.join(f'<image:image><image:loc>{BASE}figures/{name}</image:loc></image:image>' for name in FIGURES)
    urls = ''.join(f'  <url><loc>{BASE + p}</loc><lastmod>{DATA["updated"]}</lastmod>{"" if p else images}</url>\n' for p in ['', 'method.html', 'results.html'])
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + urls + '</urlset>\n'


def build() -> dict[Path, str]:
    home_tokens = {'EXTRA_META': head_meta(), 'DESCRIPTION': e(HOME_DESCRIPTION),
                   'SITE_UPDATED': f'<time datetime="{DATA["updated"]}">{human_date(DATA["updated"])}</time>'}
    outputs = {
        DOCS / 'index.html': render_home(DATA, schema('', HOME_TITLE, HOME_DESCRIPTION, home_faq()), BIB, home_faq(), home_tokens),
        DOCS / 'results.html': layout('results.html', 'ThreadBench Results — ThreadPDG, OASIS and SynthPAI', 'Explore 72 ThreadBench comparisons across 8 domains and 3 models. Inspect metric-level MWU and KS p-values, human evaluation results, and download the data.', results_page(), results_faq()),
        DOCS / 'method.html': layout('method.html', 'ThreadPDG — Planner–Writer Generation for ThreadBench', 'See how ThreadPDG plans discussions, writes comments and combines draft branches. Understand real-seed conditioning, reference pools and evaluation limits.', method_page(), method_faq()),
        DOCS / 'threadbench.bib': BIB,
        DOCS / 'llms-full.txt': llms_full(),
        DOCS / 'sitemap.xml': sitemap(),
    }
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['domain','method','model','metric','family','mwu_p_display','ks_p_display','paper_pass','domain_passes','metrics_per_domain','n_generated','n_real','paper_version'])
    for r in DATA['results']:
        for key, m in zip(DATA['metric_order'], r['metrics']):
            writer.writerow([r['domain'],r['method'],r['model'],key,METRICS[key][0],m['mwu'],m['ks'],int(m['pass']),r['passes'],12,150,150,DATA['paper_version']])
    outputs[DOCS / 'paper-results.csv'] = buf.getvalue()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    stale = []
    for path, content in build().items():
        if args.check:
            if not path.exists() or path.read_bytes() != content.encode():
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_bytes(content.encode())
            print('Built', path.relative_to(ROOT))
    if stale:
        print('Stale paper site files:', ', '.join(stale))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
