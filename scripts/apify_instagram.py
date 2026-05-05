#!/usr/bin/env python3
"""
Apify Instagram fetcher — v0.3 (URL mode).

In v0.3 the user supplies one or more Instagram post URLs they curated manually,
and this script returns a normalized list of {shortcode, image_url, caption,
owner, likes, location} dicts. Caption strings are returned in full so the
caller can mine them for content enrichment.

Usage as CLI:
    python3 apify_instagram.py URL1 URL2 ... \\
            --out /tmp/dr-meir-visuals/raw.json \\
            --download-dir /tmp/dr-meir-visuals/raw

Usage as library:
    from apify_instagram import fetch_posts, download_images
    items = fetch_posts(urls)
    paths = download_images(items, out_dir='/tmp/run/raw')

The legacy hashtag-scraper helper is kept as `fetch_by_hashtag` for back-compat,
but it is no longer called by the default v0.3 pipeline.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

CREDS_PATH = Path.home() / '.dr-meir' / 'credentials.env'


def _load_token():
    if not CREDS_PATH.exists():
        raise FileNotFoundError(f'Missing {CREDS_PATH}')
    for line in CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        if k.strip() == 'APIFY_API_TOKEN':
            return v.strip().strip('"').strip("'")
    raise ValueError('APIFY_API_TOKEN not in credentials.env')


def _shortcode_from_url(u: str):
    try:
        return u.rstrip('/').split('/p/')[1].split('/')[0]
    except Exception:
        return None


def _normalize(it):
    """Normalize a raw Apify Instagram-scraper item into our schema."""
    if not isinstance(it, dict):
        return None
    image_url = it.get('displayUrl')
    if not image_url:
        return None
    children = it.get('childPosts') or it.get('images') or []
    child_images = []
    for c in children:
        if isinstance(c, dict) and c.get('displayUrl'):
            child_images.append(c['displayUrl'])
        elif isinstance(c, str):
            child_images.append(c)
    return {
        'shortcode': it.get('shortCode') or '',
        'url': it.get('url') or '',
        'image_url': image_url,
        'child_images': child_images[:6],
        'caption': it.get('caption') or '',
        'owner': it.get('ownerUsername') or '',
        'likes': it.get('likesCount') or 0,
        'comments': it.get('commentsCount') or 0,
        'width': it.get('dimensionsWidth') or 0,
        'height': it.get('dimensionsHeight') or 0,
        'location': it.get('locationName') or '',
        'type': it.get('type') or '',
    }


def fetch_posts(urls, timeout=240):
    """Fetch Instagram posts via Apify directUrls mode.

    Returns a list of normalized items in the SAME order as the input URLs
    (when a shortcode match is found). Items the API didn't return are skipped.
    """
    token = _load_token()
    payload = json.dumps({
        'directUrls': list(urls),
        'resultsType': 'posts',
        'resultsLimit': max(50, len(urls) * 5),
        'addParentData': False,
    }).encode('utf-8')
    api = (
        'https://api.apify.com/v2/acts/'
        f'apify~instagram-scraper/run-sync-get-dataset-items?token={token}'
    )
    req = urllib.request.Request(
        api, data=payload, method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.loads(r.read())
    items = [n for n in (_normalize(it) for it in raw) if n is not None]
    by_short = {it['shortcode']: it for it in items}
    ordered = []
    for u in urls:
        sc = _shortcode_from_url(u)
        if sc and sc in by_short:
            ordered.append(by_short.pop(sc))
    ordered.extend(by_short.values())
    return ordered


def download_images(items, out_dir, include_children=False):
    """Download every item's main image to out_dir/<shortcode>.jpg.

    Returns list of (shortcode, path) tuples in the order downloaded.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for it in items:
        shortcode = it.get('shortcode') or 'unknown'
        target = out / f'{shortcode}.jpg'
        try:
            req = urllib.request.Request(
                it['image_url'], headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                target.write_bytes(r.read())
            results.append((shortcode, str(target)))
        except Exception as e:
            print(f'  download FAIL [{shortcode}]: {e}', file=sys.stderr)
        if include_children:
            for i, child in enumerate(it.get('child_images', [])):
                cpath = out / f'{shortcode}_c{i+1}.jpg'
                try:
                    req = urllib.request.Request(
                        child, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        cpath.write_bytes(r.read())
                    results.append((f'{shortcode}_c{i+1}', str(cpath)))
                except Exception as e:
                    print(f'  download FAIL [{shortcode}_c{i+1}]: {e}', file=sys.stderr)
    return results


def fetch_by_hashtag(hashtag, results_limit=30, timeout=240):
    """LEGACY (v0.2): hashtag scraper. Kept for back-compat — not used by v0.3."""
    token = _load_token()
    hashtag = hashtag.lstrip('#')
    payload = json.dumps({'hashtags': [hashtag], 'resultsLimit': results_limit}).encode('utf-8')
    api = (
        'https://api.apify.com/v2/acts/'
        f'apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={token}'
    )
    req = urllib.request.Request(
        api, data=payload, method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.loads(r.read())
    return [n for n in (_normalize(it) for it in raw) if n is not None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('urls', nargs='+', help='One or more Instagram post URLs')
    ap.add_argument('--out', default='/tmp/dr-meir-visuals/raw.json')
    ap.add_argument('--download-dir', default=None,
                    help='If set, also download images here (mkdir -p as needed)')
    ap.add_argument('--include-children', action='store_true')
    args = ap.parse_args()

    items = fetch_posts(args.urls)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'fetched {len(items)} items -> {out_path}')

    if args.download_dir:
        results = download_images(items, args.download_dir, args.include_children)
        print(f'downloaded {len(results)} images -> {args.download_dir}')
        for sc, p in results:
            print(f'  {sc} -> {p}')


if __name__ == '__main__':
    main()
