"""Integrity checks for the paper's static result publication.

These checks guard against mixing the earlier MiroBench protocol into the new
paper site and against accidentally altering rounded published decisions.
"""
from __future__ import annotations

import csv
import importlib.util
import itertools
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.duplicates = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                self.duplicates.append(attrs['id'])
            self.ids.add(attrs['id'])


class PaperSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((DOCS / 'paper-data.json').read_text())
        cls.pages = {name: Page((DOCS / name).read_text()) for name in ['index.html', 'method.html', 'results.html']}

    def test_corpus_inventory(self):
        ds = self.data['domains']
        self.assertEqual(len(ds), 8)
        self.assertEqual(sum(d['threads'] for d in ds), 9817)
        self.assertEqual(self.data['reported_total_subdomains'], 116)
        # Preserve and flag the source's arithmetic discrepancy rather than inventing a correction.
        self.assertEqual(sum(d['subdomains'] for d in ds), 117)
        self.assertIn('summing to 117', self.data['source']['inventory_note'])
        metrics = [m[0] for f in self.data['families'] for m in f['metrics']]
        self.assertEqual(len(metrics), 12)
        self.assertEqual(set(metrics), set(self.data['metric_order']))
        self.assertEqual([f['name'] for f in self.data['families']], ['Uniformity', 'Expression', 'Tone', 'Interaction'])

    def test_full_factorial_results_and_decisions(self):
        ds = [d['name'] for d in self.data['domains']]
        expected = set(itertools.product(ds, ['ThreadPDG','OASIS','SynthPAI'], ['gpt-5.4-mini','gpt-4o-mini','DeepSeek-V4.1-Flash']))
        rows = self.data['results']
        self.assertEqual(len(rows), 72)
        self.assertEqual({(r['domain'],r['method'],r['model']) for r in rows}, expected)
        for r in rows:
            self.assertEqual(len(r['metrics']), 12)
            self.assertEqual(sum(m['pass'] for m in r['metrics']), r['passes'])
            for m in r['metrics']:
                self.assertIsInstance(m['pass'], bool)
                for name in ['mwu', 'ks']:
                    self.assertGreaterEqual(float(m[name].removeprefix('<')), 0)
                    self.assertLessEqual(float(m[name].removeprefix('<')), 1)
        # Published boundary cases: rounded .05 values can pass or fail.
        celebrity = next(r for r in rows if (r['domain'],r['method'],r['model']) == ('Celebrity','ThreadPDG','DeepSeek-V4.1-Flash'))
        self.assertEqual({k:celebrity['metrics'][5][k] for k in ['mwu','ks','pass']}, {'mwu':'.05','ks':'.20','pass':True})
        celebrity_gpt = next(r for r in rows if (r['domain'],r['method'],r['model']) == ('Celebrity','ThreadPDG','gpt-5.4-mini'))
        self.assertEqual({k:celebrity_gpt['metrics'][8][k] for k in ['mwu','ks','pass']}, {'mwu':'.05','ks':'.06','pass':False})

    def test_model_specific_headline_ranges(self):
        expected = {'gpt-5.4-mini':(8,11), 'DeepSeek-V4.1-Flash':(7,12), 'gpt-4o-mini':(2,5)}
        for model, bounds in expected.items():
            counts = [r['passes'] for r in self.data['results'] if r['method']=='ThreadPDG' and r['model']==model]
            self.assertEqual((min(counts),max(counts)), bounds)

    def test_revised_reference_and_distance_coverage(self):
        references = self.data['real_reference']
        self.assertEqual(set(references), {d['name'] for d in self.data['domains']})
        for domain in references.values():
            self.assertEqual(set(domain), set(self.data['metric_order']))
            for metric in domain.values():
                self.assertGreaterEqual(metric['w1'], 0)
                self.assertTrue(0 <= metric['cliffs'] <= 1)
                self.assertTrue(0 <= metric['mwu_pass_rate'] <= 100)
                self.assertTrue(0 <= metric['ks_pass_rate'] <= 100)
        self.assertEqual(references['Camera']['self_bleu_4']['w1'], 0.0055)
        self.assertEqual(references['Camera']['self_bleu_4']['mwu_pass_rate'], 94.5)
        for row in self.data['results']:
            for metric in row['metrics']:
                self.assertGreaterEqual(metric['w1'], 0)
                self.assertTrue(0 <= metric['cliffs'] <= 1)

    def test_csv_keeps_every_published_metric(self):
        with (DOCS/'paper-results.csv').open(newline='') as f:
            exported = list(csv.DictReader(f))
        self.assertEqual(len(exported), 864)
        for group in self.data['results']:
            for key, metric in zip(self.data['metric_order'], group['metrics']):
                row = exported.pop(0)
                self.assertEqual((row['domain'],row['method'],row['model'],row['metric']), (group['domain'],group['method'],group['model'],key))
                self.assertEqual((row['mwu_p_display'],row['ks_p_display'],row['paper_pass']), (metric['mwu'],metric['ks'],str(int(metric['pass']))))
                self.assertEqual((row['n_generated'],row['n_real']), ('150','150'))

    def test_static_html_structure_and_links(self):
        for name, page in self.pages.items():
            self.assertFalse(page.duplicates, (name,page.duplicates))
            self.assertEqual(sum(tag=='h1' for tag,_ in page.tags),1,name)
            self.assertEqual(sum(tag=='main' for tag,_ in page.tags),1,name)
            self.assertTrue(any(tag=='html' and a.get('lang')=='en' for tag,a in page.tags))
            for tag, attrs in page.tags:
                if tag=='img':
                    for key in ['alt','width','height']:
                        self.assertTrue(attrs.get(key),(name,key))
                for key in ['href','src']:
                    if key not in attrs:
                        continue
                    parsed=urlsplit(attrs[key])
                    if parsed.scheme or parsed.netloc:
                        continue
                    target=(DOCS / unquote(parsed.path)).resolve() if parsed.path else DOCS/name
                    if target.is_dir():
                        target=target/'index.html'
                    self.assertTrue(target.exists(),(name,attrs[key]))
                    if parsed.fragment and target.suffix=='.html':
                        ids=Page(target.read_text()).ids
                        self.assertIn(unquote(parsed.fragment),ids,(name,attrs[key]))

    def test_metadata_and_research_boundaries(self):
        import re
        for name in self.pages:
            text=(DOCS/name).read_text()
            graph=json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>',text).group(1))['@graph']
            paper=next(n for n in graph if n['@type']=='ScholarlyArticle')
            self.assertEqual(len(paper['author']),7)
            self.assertEqual(paper['url'],'https://arxiv.org/abs/2606.14715')
            self.assertNotIn('MiroBench_preprint.pdf',text)
            self.assertNotIn('cdn.tailwindcss.com',text)
            canonical=next(a['href'] for tag,a in self.pages[name].tags if tag=='link' and a.get('rel')=='canonical')
            self.assertEqual(canonical, 'https://yyu6.github.io/ThreadBench/'+('' if name=='index.html' else name))
        results=(DOCS/'results.html').read_text()
        self.assertEqual(results.count('data-result-row'),72)
        self.assertEqual(results.count('class="metric-verdict '),864)
        self.assertIn('not proof of equivalence',results)
        self.assertIn('Ties are excluded',results)
        self.assertIn('earlier MiroBench implementation',(DOCS/'index.html').read_text())
        self.assertIn('id="sunburst"',(DOCS/'index.html').read_text())
        self.assertIn('id="live-thread"',(DOCS/'index.html').read_text())
        self.assertIn('complete real seed',(DOCS/'method.html').read_text())
        self.assertIn('noindex,follow',(DOCS/'leaderboard.html').read_text())
        self.assertNotIn('leaderboard.html',(DOCS/'sitemap.xml').read_text())

    def test_generated_files_are_current(self):
        spec=importlib.util.spec_from_file_location('paper_site_build',ROOT/'scripts/build_paper_site.py')
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for path, content in mod.build().items():
            self.assertEqual(path.read_bytes(),content.encode(),str(path))


if __name__ == '__main__':
    unittest.main()
