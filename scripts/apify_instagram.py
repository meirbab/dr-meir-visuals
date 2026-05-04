#!/usr/bin/env python3
"""
Search Instagram via Apify for visual inspiration.

Usage:
    python3 apify_instagram.py <hashtag_or_keyword> [--limit 30]

Returns JSON list of candidates:
    [
      {
        "url": "https://...",
        "image_url": "https://...",
        "caption": "...",
        "likes": 1234,
        "width": 1080, "height": 1080,
        "owner": "...",
        "type": "image"
      },
      ...
    ]

Filters out videos, carousels, low-engagement posts, low-res images.
Drops posts that look like ads / promo (heavy emoji, "купить", "DM", etc.).

Reads APIFY_API_TOKEN from ~/.dr-meir/credentials.env.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


def load_creds():
    creds_path = Path.home() / '.dr-meir' / 'credentials.env'
    creds = {}
    for line in creds_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        creds[k.strip()] = v.strip().strip('"').strip("'")
    return creds


PROMO_RE = re.compile(r'(купить|cкид|sale|promo|акци[яи]|записаться|запись|dm me|whatsapp|☎️|📞)',
                      re.IGNORECASE)


def looks_promo(caption: str) -> bool:
    if not caption:
        return False
    return bool(PROMO_RE.search(caption))


def run_hashtag_scraper(hashtag: str, results_limit: int = 30, token: str = None):
    """Run apify/instagram-hashtag-scraper synchronously and return dataset items.

    Note: drops the leading '#' if present. The actor expects bare names.
    """
    token = token or load_creds()['APIFY_API_TOKEN']
    hashtag = hashtag.lstrip('#')

    url = f'https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={token}'
    payload = json.dumps({
        'hashtags': [hashtag],
        'resultsLimit': results_limit,
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, method='POST', headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=240) as r:
        items = json.loads(r.read().decode('utf-8'))
    return items if isinstance(items, list) else []


def filter_candidates(items, min_likes=50, min_dim=800):
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get('type', '').lower() not in ('image', 'photo', 'sidecar'):
            continue
        if (it.get('likesCount') or 0) < min_likes:
            continue
        w = it.get('dimensionsWidth') or it.get('width') or 0
        h = it.get('dimensionsHeight') or it.get('height') or 0
        if w and w < min_dim:
            continue
        if h and h < min_dim:
            continue
        if looks_promo(it.get('caption') or ''):
            continue
        out.append({
            'url': it.get('url'),
            'image_url': it.get('displayUrl') or it.get('imageUrl'),
            'caption': (it.get('caption') or '')[:500],
            'likes': it.get('likesCount') or 0,
            'comments': it.get('commentsCount') or 0,
            'width': w,
            'height': h,
            'owner': it.get('ownerUsername') or '',
            'timestamp': it.get('timestamp') or '',
            'hashtags': it.get('hashtags') or [],
        })
    out.sort(key=lambda x: -x['likes'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('keyword', help='Hashtag or keyword (Russian recommended)')
    ap.add_argument('--limit', type=int, default=30)
    ap.add_argument('--min-likes', type=int, default=50)
    ap.add_argument('--min-dim', type=int, default=800)
    args = ap.parse_args()

    items = run_hashtag_scraper(args.keyword, args.limit)
    filtered = filter_candidates(items, args.min_likes, args.min_dim)
    print(json.dumps(filtered, ensure_ascii=False, indent=2))
    print(f'\n# {len(filtered)} candidates after filter (from {len(items)} raw)', file=sys.stderr)


if __name__ == '__main__':
    main()
