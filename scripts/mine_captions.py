#!/usr/bin/env python3
"""
mine_captions.py — extract enrichment-worthy facts from IG captions.

Claude does the actual semantic extraction (Hebrew translation + clinical
filtering). This script is the deterministic helper: it loads captions, the
target post body, and produces a structured "candidate facts" report — including
duplicates against existing on-page text. Claude reads the report and produces
the final Hebrew block + FAQs.

Usage:
    python3 mine_captions.py \
        --raw /tmp/dr-meir-visuals/raw.json \
        --post-id 52464 \
        --out /tmp/dr-meir-visuals/mined_facts.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / '.dr-meir'
sys.path.insert(0, str(ROOT / 'lib'))
from wp_client import get_post  # noqa: E402


# Patterns we look for in source-language captions:
PATTERNS = {
    'percentages': re.compile(r'(\d{1,3})\s*%'),
    'mechanism_terms': re.compile(
        r'(альфа|бета|alpha|beta|adipocyte|липол|липогенез|cellulit|целлюлит|'
        r'гормон|hormonal|estrog|тестостерон|testosterone|catecholamine|катехоламин|'
        r'локальные жировые отложения|жировые ловушки|fat trap|stubborn fat)',
        re.IGNORECASE),
    'multi_area': re.compile(
        r'(внешн|передн|внутренн|циркуляр|икр|щиколот|колен|галиф|'
        r'thigh|calf|knee|ankle|saddle|inner|outer|circumferent)',
        re.IGNORECASE),
    'recovery_terms': re.compile(
        r'(восстанов|реабил|recover|return\s+to\s+work|swelling|отёк|'
        r'компресс|compression|стационар|day\s+\d+|неделя|week\s+\d+)',
        re.IGNORECASE),
    'stat_phrase': re.compile(
        r'(by\s+statistic|по\s+статистике|статистич|study\s+sh|исследован|клиническ)',
        re.IGNORECASE),
}

# Strip the Hebrew text editor body from the post into searchable plain
HE_TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')


def strip_html(html):
    return WS_RE.sub(' ', HE_TAG_RE.sub(' ', html or '')).strip()


def collect_post_body(post_meta_data):
    tree = json.loads(post_meta_data or '[]')
    chunks = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            wt = node.get('widgetType')
            settings = node.get('settings') or {}
            if wt == 'heading':
                chunks.append(settings.get('title', ''))
            elif wt == 'text-editor':
                chunks.append(strip_html(settings.get('editor', '')))
            elif wt == 'toggle':
                for tab in (settings.get('tabs') or []):
                    chunks.append(tab.get('tab_title', ''))
                    chunks.append(strip_html(tab.get('tab_content', '')))
            for c in node.get('elements', []) or []:
                walk(c)
    walk(tree)
    return '\n'.join(chunks)


def signals(caption):
    out = {'percentages': [], 'mechanism': [], 'multi_area': [],
           'recovery': [], 'has_stat_framing': False}
    for m in PATTERNS['percentages'].finditer(caption):
        out['percentages'].append(m.group(0))
    for m in PATTERNS['mechanism_terms'].finditer(caption):
        out['mechanism'].append(m.group(0).lower())
    for m in PATTERNS['multi_area'].finditer(caption):
        out['multi_area'].append(m.group(0).lower())
    for m in PATTERNS['recovery_terms'].finditer(caption):
        out['recovery'].append(m.group(0).lower())
    if PATTERNS['stat_phrase'].search(caption):
        out['has_stat_framing'] = True
    out['mechanism'] = sorted(set(out['mechanism']))
    out['multi_area'] = sorted(set(out['multi_area']))
    out['recovery'] = sorted(set(out['recovery']))
    return out


def already_in_page(text, page_body):
    """Cheap n-gram membership: is this fragment already in the page?"""
    t = text.strip().lower()
    if not t:
        return True
    return t in page_body.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True, help='Path to apify raw.json with captions')
    ap.add_argument('--post-id', type=int, required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    items = json.loads(Path(args.raw).read_text(encoding='utf-8'))
    post = get_post(args.post_id)
    body = collect_post_body(post.get('meta', {}).get('_elementor_data') or '[]')

    report = {
        'post_id': args.post_id,
        'post_link': post.get('link'),
        'post_title': post.get('title', {}).get('rendered', ''),
        'sources': [],
    }
    for it in items:
        cap = it.get('caption') or ''
        sig = signals(cap)
        report['sources'].append({
            'shortcode': it.get('shortcode'),
            'owner': it.get('owner'),
            'url': it.get('url'),
            'language_hint': 'ru' if re.search(r'[а-яА-Я]', cap) else (
                'es' if re.search(r'[ñáéíóú]', cap, re.I) else 'en'),
            'caption_full': cap,
            'caption_excerpt': cap[:600],
            'signals': sig,
            'percentages_already_on_page': [
                p for p in sig['percentages'] if p in body
            ],
            'percentages_new': [
                p for p in sig['percentages'] if p not in body
            ],
        })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                              encoding='utf-8')
    print(f'Wrote {args.out}')
    print(f'  sources: {len(report["sources"])}')
    print('Note: Claude must read this report and synthesize the Hebrew')
    print('enrichment block + FAQ items. The script does not invent text.')


if __name__ == '__main__':
    main()
