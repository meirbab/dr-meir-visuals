#!/usr/bin/env python3
"""
Inject a visual block (figure HTML) into an Elementor post.

Usage:
    python3 inject_visual.py <post_id> --html-file <html_path> --marker <unique_marker> [--needle <text_to_locate>]

Options:
    --needle TEXT   Text to locate the target widget. The block is inserted right after
                    the </ol>, </ul>, </h2>, or </p> closest to the needle. If omitted,
                    block is appended to the end of the largest text-editor widget.
    --replace-old MARKER  If provided, removes any prior block with this marker before injecting.

The injected block must already start with `<!-- {marker} -->` and end with `</figure>` (or any closing tag).
This makes future re-runs idempotent.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path.home() / '.dr-meir'
sys.path.insert(0, str(ROOT / 'lib'))

from wp_client import get_post, update_elementor, clear_elementor_cache, submit_indexnow


def find_widgets(node, results=None):
    """Walk the tree, collect text-editor widget refs."""
    if results is None:
        results = []
    if isinstance(node, list):
        for n in node:
            find_widgets(n, results)
        return results
    if isinstance(node, dict):
        if node.get('widgetType') == 'text-editor':
            results.append(node)
        children = node.get('elements', []) or []
        if isinstance(children, list):
            for c in children:
                find_widgets(c, results)
    return results


def remove_block(html: str, marker: str) -> str:
    """Strip a previously-injected block by its HTML comment marker.
    Block format: <!-- {marker} -->\\n<figure ...>...</figure>"""
    start_token = f'<!-- {marker} -->'
    if start_token not in html:
        return html
    start = html.index(start_token)
    end_marker = '</figure>'
    end_idx = html.find(end_marker, start)
    if end_idx == -1:
        return html
    end = end_idx + len(end_marker)
    while end < len(html) and html[end] in '\n\r ':
        end += 1
    return html[:start] + html[end:]


def insert_after_closest(html: str, needle: str, block: str) -> str:
    """Find the section containing needle; insert block after the next major closer."""
    if needle and needle in html:
        ndx = html.index(needle)
        # Find the closest closing tag AFTER the needle
        for closer in ('</ol>', '</ul>', '</h2>', '</h3>', '</p>'):
            idx = html.find(closer, ndx)
            if idx != -1:
                end = idx + len(closer)
                return html[:end] + '\n' + block + html[end:]
    # Fallback: append to end of html
    return html + '\n' + block


def run(post_id, html_file, marker, needle=None, replace_old=None, dry_run=False):
    block = Path(html_file).read_text(encoding='utf-8')

    print(f'Fetching post {post_id}...')
    post = get_post(post_id)
    elementor_str = post.get('meta', {}).get('_elementor_data') or '[]'
    link = post.get('link', '')

    if marker in elementor_str:
        print('SKIP — current marker already present')
        return {'status': 'skip-already-present'}

    tree = json.loads(elementor_str)
    widgets = find_widgets(tree)
    print(f'Found {len(widgets)} text-editor widget(s)')

    # Step 1: remove old version blocks (if requested)
    if replace_old:
        for w in widgets:
            ed = w.get('settings', {}).get('editor', '')
            if isinstance(ed, str) and replace_old in ed:
                w['settings']['editor'] = remove_block(ed, replace_old)
                print(f'  Removed old block "{replace_old}"')

    # Step 2: locate target widget by needle
    target = None
    if needle:
        for w in widgets:
            ed = w.get('settings', {}).get('editor', '')
            if isinstance(ed, str) and needle in ed:
                target = w
                break

    # Fallback: largest non-lhub widget
    if target is None:
        non_hub = [w for w in widgets if not w.get('id', '').startswith('lhub')]
        target = max(non_hub, key=lambda w: len(w.get('settings', {}).get('editor', '') or ''),
                     default=None)

    if target is None:
        print('ERROR: no suitable widget found')
        return {'status': 'error-no-widget'}

    existing = target['settings']['editor']
    new_html = insert_after_closest(existing, needle or '', block)
    target['settings']['editor'] = new_html

    new_data = json.dumps(tree, ensure_ascii=False)
    print(f'Pushing — size {len(elementor_str)} -> {len(new_data)}')

    if dry_run:
        return {'status': 'dry-run', 'size': len(new_data)}

    update_elementor(post_id, new_data, clear_css=True)
    clear_elementor_cache()
    time.sleep(2)
    try:
        ir = submit_indexnow(link)
    except Exception as e:
        ir = {'error': str(e)}
    return {'status': 'pushed', 'url': link, 'indexnow': ir}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('post_id', type=int)
    ap.add_argument('--html-file', required=True, help='Path to HTML block file')
    ap.add_argument('--marker', required=True, help='Unique HTML comment marker (e.g. fat_diagram_v3)')
    ap.add_argument('--needle', default=None, help='Text to locate target widget')
    ap.add_argument('--replace-old', default=None, help='Old marker to strip before injection')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    out = run(args.post_id, args.html_file, args.marker,
              args.needle, args.replace_old, args.dry_run)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
