#!/usr/bin/env python3
"""
orchestrate.py — v0.3 IG-links pipeline runner.

This script is a **planner**: it validates inputs, sets up the working dir,
and emits a structured plan listing the exact MCP/Bash steps Claude should
execute. It does NOT call MCP tools itself.

Usage:
    python3 orchestrate.py <target> --ig URL1 [URL2 ...] [--brief "..."] \\
                                    [--mode auto|semi|interactive] \\
                                    [--skip-video] [--skip-text] \\
                                    [--video-count N]

`<target>` is either a post id or a full dr-meir.com URL.

The plan emitted lists, in order, the steps:
  1. apify_instagram fetch + download
  2. per-image NSFW guard (Pillow crop) + Higgsfield upload + nano_banana_2 edit
  3. morph video preparation + Kling 3.0 generate (unless --skip-video)
  4. WP media uploads
  5. gallery + video widget swap (replace_galleries_with_media.py)
  6. caption mining → enrichment plan (unless --skip-text)
  7. push, clear cache, IndexNow, verify live
"""
import argparse
import json
import re
import sys
from pathlib import Path


def parse_target(arg):
    if arg.isdigit():
        return int(arg), None
    m = re.search(r'/[^/]+/([^/]+)/?$', arg)
    if m:
        return None, m.group(1)
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='Post id or full URL on dr-meir.com')
    ap.add_argument('--ig', nargs='+', required=True,
                    help='One or more Instagram post URLs (manually curated)')
    ap.add_argument('--brief', default='',
                    help='Free-text intent. If empty, default cleaning + 1 video + caption mining.')
    ap.add_argument('--mode', choices=['auto', 'semi', 'interactive'], default='auto')
    ap.add_argument('--skip-video', action='store_true')
    ap.add_argument('--skip-text', action='store_true')
    ap.add_argument('--video-count', type=int, default=1)
    ap.add_argument('--run-id', default=None)
    args = ap.parse_args()

    if not args.ig or not all(u.startswith('http') for u in args.ig):
        print('ERROR: at least one IG URL required', file=sys.stderr)
        sys.exit(2)

    post_id, slug = parse_target(args.target)
    run_id = args.run_id or f'run-{__import__("time").strftime("%Y%m%d-%H%M%S")}'
    work = Path('/tmp/dr-meir-visuals') / run_id
    work.mkdir(parents=True, exist_ok=True)

    plan = {
        'run_id': run_id,
        'workdir': str(work),
        'target': {'arg': args.target, 'post_id': post_id, 'slug': slug},
        'instagram_links': args.ig,
        'brief': args.brief,
        'mode': args.mode,
        'video_count': 0 if args.skip_video else max(args.video_count, 1),
        'mine_text': not args.skip_text,
        'steps': [
            {
                'id': '1-fetch',
                'name': 'Fetch IG posts via Apify (URL mode)',
                'cmd': [
                    'python3', 'scripts/apify_instagram.py',
                    *args.ig,
                    '--out', str(work / 'raw.json'),
                    '--download-dir', str(work / 'raw'),
                ],
            },
            {
                'id': '2-clean',
                'name': 'For each image: NSFW pre-crop + Higgsfield nano_banana_2 edit',
                'description':
                    'Use Higgsfield MCP. Default cleaning prompt from '
                    'templates/clean_default.txt. NSFW fallback: tighter Pillow crop '
                    'or mcp__nano-banana__edit_image.',
                'planner_helper': 'scripts/clean_image_higgsfield.py plan ...',
                'output': str(work / 'clean'),
            },
            {
                'id': '3-video',
                'name': f'Generate {0 if args.skip_video else max(args.video_count, 1)} '
                        'transformation morph video(s) via Higgsfield Kling 3.0',
                'enabled': not args.skip_video,
                'planner_helper': 'scripts/generate_morph_video.py prepare ...',
                'output': str(work / 'video'),
            },
            {
                'id': '4-upload',
                'name': 'Upload all cleaned images + videos to WP media library',
                'helper': 'scripts/wp_media.py',
            },
            {
                'id': '5-galleries',
                'name': 'Swap galleries on the target post (last gallery → video widget)',
                'helper': 'scripts/replace_galleries_with_media.py',
                'plan_file': str(work / 'gallery_plan.json'),
            },
            {
                'id': '6-text',
                'name': 'Mine captions → enrichment text + new FAQs',
                'enabled': not args.skip_text,
                'helper': 'scripts/mine_captions.py',
                'mined_facts_file': str(work / 'mined_facts.json'),
                'output_block': str(work / 'enrichment_block.html'),
            },
            {
                'id': '7-push',
                'name': 'update_elementor + clear_elementor_cache + submit_indexnow + verify live',
                'helper': '~/.dr-meir/lib/wp_client.py',
            },
        ],
    }

    plan_path = work / 'plan.json'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                         encoding='utf-8')
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print(f'\n# Plan saved to {plan_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
