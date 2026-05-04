#!/usr/bin/env python3
"""
Extract Hebrew keywords from a dr-meir.com WordPress post.

Usage:
    python3 extract_keywords.py <post_id>

Outputs JSON with:
    - h1: primary heading text
    - h2_list: all H2 headings (section topics)
    - h3_list: all H3 headings
    - focus_keyword: Rank Math focus keyword
    - meta_description: Rank Math meta description
    - body_text: cleaned body text (for vision-prompt context)
    - title: post title
    - link: post URL
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / '.dr-meir'
sys.path.insert(0, str(ROOT / 'lib'))

from wp_client import get_post


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '')


def walk_widgets(node, results):
    if isinstance(node, list):
        for n in node:
            walk_widgets(n, results)
        return
    if not isinstance(node, dict):
        return
    wt = node.get('widgetType')
    settings = node.get('settings', {}) or {}
    if isinstance(settings, dict):
        if wt == 'text-editor':
            results['text_blocks'].append(settings.get('editor', '') or '')
        elif wt == 'heading':
            results['headings'].append(settings.get('title', '') or '')
        elif wt == 'toggle':
            for tab in settings.get('tabs', []) or []:
                if isinstance(tab, dict):
                    results['faq_qs'].append(tab.get('tab_title', '') or '')
                    results['text_blocks'].append(tab.get('tab_content', '') or '')
    for c in node.get('elements', []) or []:
        walk_widgets(c, results)


def extract(post_id):
    post = get_post(post_id)
    title = post.get('title', {}).get('rendered', '')
    link = post.get('link', '')
    meta = post.get('meta', {}) or {}
    elementor_str = meta.get('_elementor_data') or '[]'

    tree = json.loads(elementor_str)
    results = {'text_blocks': [], 'headings': [], 'faq_qs': []}
    walk_widgets(tree, results)

    # Pull H1 from text blocks (first <h1>) or fall back to title
    h1 = None
    for tb in results['text_blocks']:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', tb, re.DOTALL)
        if m:
            h1 = strip_html(m.group(1)).strip()
            break

    # Pull H2 / H3 from text blocks AND from heading widgets
    h2_list = []
    h3_list = []
    for tb in results['text_blocks']:
        h2_list.extend(strip_html(m).strip() for m in re.findall(r'<h2[^>]*>(.*?)</h2>', tb, re.DOTALL))
        h3_list.extend(strip_html(m).strip() for m in re.findall(r'<h3[^>]*>(.*?)</h3>', tb, re.DOTALL))
    for hd in results['headings']:
        # heading widgets are usually H2 by default
        if hd.strip():
            h2_list.append(hd.strip())

    body_text = '\n'.join(strip_html(tb).strip() for tb in results['text_blocks'])
    body_text = re.sub(r'\n{3,}', '\n\n', body_text).strip()

    return {
        'post_id': post_id,
        'title': strip_html(title),
        'link': link,
        'h1': h1 or strip_html(title),
        'h2_list': h2_list,
        'h3_list': h3_list,
        'faq_questions': results['faq_qs'],
        'focus_keyword': meta.get('rank_math_focus_keyword', ''),
        'meta_description': meta.get('rank_math_description', ''),
        'body_text_preview': body_text[:2000],
        'body_word_count': len(body_text.split()),
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: extract_keywords.py <post_id>', file=sys.stderr)
        sys.exit(1)
    out = extract(int(sys.argv[1]))
    print(json.dumps(out, ensure_ascii=False, indent=2))
