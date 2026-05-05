#!/usr/bin/env python3
"""
replace_galleries_with_media.py — generic gallery + video swap helper for v0.3.

Walks an Elementor tree (full _elementor_data JSON), finds gallery widgets by
widgetType=='gallery', and either:
  - replaces settings.gallery with new image refs, OR
  - replaces the entire widget node with a hosted-video widget (preserves the
    original `id` so any custom CSS still binds).

Usage:
    python3 replace_galleries_with_media.py <post_id> --plan plan.json [--dry-run]

plan.json schema:
    {
      "galleries": [
        {"id": "dc9fd61", "type": "images",
         "items": [{"id": 52546, "url": "https://..."}, ...]},
        {"id": "b6a0abb", "type": "images",
         "items": [{"id": 52547, "url": "https://..."}, ...]},
        {"id": "4290ce8", "type": "video",
         "video_url": "https://.../knee-transformation-morph.mp4",
         "poster_id": 52546, "poster_url": "https://...",
         "alt": "..."}
      ]
    }
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path.home() / '.dr-meir'
sys.path.insert(0, str(ROOT / 'lib'))
from wp_client import (  # noqa: E402
    get_post,
    update_elementor,
    clear_elementor_cache,
    submit_indexnow,
)


def replace_gallery_node(tree, gallery_id, items):
    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if isinstance(node, dict):
            if node.get('widgetType') == 'gallery' and node.get('id') == gallery_id:
                node.setdefault('settings', {})['gallery'] = items
                return
            for c in node.get('elements', []) or []:
                walk(c)
    walk(tree)


def swap_to_video(tree, gallery_id, video_url, poster_url, poster_id, alt=''):
    def walk(node):
        if isinstance(node, list):
            for i, n in enumerate(node):
                if isinstance(n, dict) and n.get('widgetType') == 'gallery' \
                        and n.get('id') == gallery_id:
                    node[i] = {
                        'id': gallery_id,
                        'elType': 'widget',
                        'widgetType': 'video',
                        'isInner': False,
                        'isLocked': False,
                        'settings': {
                            'video_type': 'hosted',
                            'hosted_url': {
                                'id': '',
                                'url': video_url,
                                'source': 'library',
                            },
                            'autoplay': 'yes',
                            'loop': 'yes',
                            'mute': 'yes',
                            'play_on_mobile': 'yes',
                            'controls': '',
                            'image_overlay': {
                                'id': poster_id,
                                'url': poster_url,
                                'size': 'full',
                                'alt': alt,
                                'source': 'library',
                            },
                            'show_image_overlay': 'yes',
                            'lazy_load': 'yes',
                            'aspect_ratio': '11',
                            'lightbox': '',
                        },
                        'elements': [],
                    }
                    return
                else:
                    walk(n)
            return
        if isinstance(node, dict):
            els = node.get('elements')
            if isinstance(els, list):
                walk(els)
    walk(tree)


def apply_plan(tree, plan):
    for entry in plan.get('galleries', []):
        gid = entry['id']
        if entry['type'] == 'images':
            replace_gallery_node(tree, gid, entry['items'])
        elif entry['type'] == 'video':
            swap_to_video(
                tree, gid,
                video_url=entry['video_url'],
                poster_url=entry['poster_url'],
                poster_id=entry['poster_id'],
                alt=entry.get('alt', ''),
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('post_id', type=int)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    post = get_post(args.post_id)
    elementor_str = post.get('meta', {}).get('_elementor_data') or '[]'
    tree = json.loads(elementor_str)

    apply_plan(tree, plan)
    new_data = json.dumps(tree, ensure_ascii=False)
    print(f'Pushing — size {len(elementor_str)} -> {len(new_data)}')

    if args.dry_run:
        print(json.dumps({'status': 'dry-run', 'size': len(new_data)}))
        return

    update_elementor(args.post_id, new_data, clear_css=True)
    clear_elementor_cache()
    time.sleep(2)
    try:
        ir = submit_indexnow(post.get('link', ''))
        print(f'IndexNow: {ir}')
    except Exception as e:
        print(f'IndexNow ERROR: {e}')
    print(f'Done. Live: {post.get("link","")}')


if __name__ == '__main__':
    main()
