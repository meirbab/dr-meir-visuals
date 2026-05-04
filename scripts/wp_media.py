#!/usr/bin/env python3
"""
Upload an image or video file to dr-meir.com WP media library, with Hebrew alt/title/caption.

Usage:
    python3 wp_media.py <file_path> --filename slug.png \
                                    --alt "תיאור עברית" \
                                    --title "כותרת" \
                                    --caption "כיתוב מלא"

Returns JSON: {id, source_url, alt, title}
"""
import argparse
import json
import mimetypes
import os
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


def upload(file_path: str, filename: str, alt: str = '', title: str = '', caption: str = ''):
    creds = load_creds()
    site = creds['WP_SITE'].rstrip('/')
    user = creds['WP_USERNAME']
    pwd = creds['WP_APP_PASSWORD']

    import base64
    auth = base64.b64encode(f'{user}:{pwd}'.encode()).decode()

    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    with open(file_path, 'rb') as f:
        data = f.read()

    req = urllib.request.Request(
        f'{site}/wp-json/wp/v2/media',
        data=data, method='POST',
        headers={
            'Authorization': f'Basic {auth}',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': content_type,
        })
    with urllib.request.urlopen(req, timeout=180) as r:
        meta = json.loads(r.read().decode('utf-8'))

    media_id = meta.get('id')

    # Update meta with Hebrew labels
    if any([alt, title, caption]):
        update_payload = {}
        if alt:     update_payload['alt_text'] = alt
        if title:   update_payload['title'] = title
        if caption: update_payload['caption'] = caption
        body = json.dumps(update_payload).encode('utf-8')
        req2 = urllib.request.Request(
            f'{site}/wp-json/wp/v2/media/{media_id}',
            data=body, method='POST',
            headers={
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json',
            })
        with urllib.request.urlopen(req2, timeout=60) as r:
            meta = json.loads(r.read().decode('utf-8'))

    return {
        'id': meta.get('id'),
        'source_url': meta.get('source_url'),
        'alt': meta.get('alt_text', ''),
        'title': meta.get('title', {}).get('rendered', ''),
        'mime_type': meta.get('mime_type', ''),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file_path')
    ap.add_argument('--filename', required=True)
    ap.add_argument('--alt', default='')
    ap.add_argument('--title', default='')
    ap.add_argument('--caption', default='')
    args = ap.parse_args()

    result = upload(args.file_path, args.filename, args.alt, args.title, args.caption)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
