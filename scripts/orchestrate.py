#!/usr/bin/env python3
"""
Orchestrator — runs the full dr-meir-visuals pipeline for a single post.

Usage:
    python3 orchestrate.py <post_id> --path A|B|C [options]

Path A (diagram):
    --topic-needle "שומן תת-עורי"   # locate target widget
    --diagram-prompt "..."          # passed to nano-banana
    --title "..."                   # Hebrew figure title
    --labels labels.json            # array of {bg,accent,title_color,title,body,badge}
    --slug-prefix abdominal-fat     # used for filename

Path B (image transform):
    --keyword-ru "липосакция"       # Russian keyword for Apify
    --topic-needle "..."
    --transform-prompt "..."        # how to transform via nano-banana edit

Path C (video, before/after):
    --before-image /path/to/before.jpg
    --after-image  /path/to/after.jpg
    --duration 4
    --topic-needle "..."

Common options:
    --mode auto|semi|interactive   # default semi
    --dry-run

This script doesn't call MCP tools directly (Claude does that). Instead it:
    1. Validates inputs
    2. Prepares the working directory
    3. Prints structured next steps for Claude to execute
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('post_id', type=int)
    ap.add_argument('--path', choices=['A', 'B', 'C'], required=True)
    ap.add_argument('--topic-needle', help='Text to locate target widget')
    ap.add_argument('--diagram-prompt', help='nano-banana prompt for path A')
    ap.add_argument('--title', help='Hebrew figure title')
    ap.add_argument('--labels', help='Path to labels JSON for path A')
    ap.add_argument('--keyword-ru', help='Russian keyword for path B Apify search')
    ap.add_argument('--transform-prompt', help='nano-banana edit prompt for path B')
    ap.add_argument('--before-image', help='Path to before image (path C)')
    ap.add_argument('--after-image', help='Path to after image (path C)')
    ap.add_argument('--duration', type=int, default=4, help='Video seconds (path C)')
    ap.add_argument('--slug-prefix', default='visual')
    ap.add_argument('--mode', choices=['auto', 'semi', 'interactive'], default='semi')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    workdir = Path.home() / '.dr-meir' / 'campaigns' / 'dr-meir-visuals' / f'post-{args.post_id}'
    workdir.mkdir(parents=True, exist_ok=True)

    plan = {
        'post_id': args.post_id,
        'path': args.path,
        'mode': args.mode,
        'workdir': str(workdir),
        'next_steps': [],
    }

    if args.path == 'A':
        plan['next_steps'] = [
            f"1. Run extract_keywords.py {args.post_id} → save to {workdir}/keywords.json",
            f"2. Build diagram prompt from H2 + topic-needle context",
            f"3. Call mcp__nano-banana__generate_image (no Hebrew text in image)",
            f"4. If text appeared, edit_image to strip ALL labels",
            f"5. Build figure HTML from templates/diagram_overlay.html with labels",
            f"6. Upload via wp_media.py → get media_id + source_url",
            f"7. Call inject_visual.py with --marker {args.slug_prefix}_v1 --needle '{args.topic_needle}'",
            f"8. Verify live with cache-bust",
        ]
    elif args.path == 'B':
        plan['next_steps'] = [
            f"1. extract_keywords.py {args.post_id}",
            f"2. apify_instagram.py '{args.keyword_ru}' --limit 30 → {workdir}/candidates.json",
            f"3. For top 20: download to {workdir}/inputs/, then Read each via vision",
            f"4. Score each (relevance, quality, style, watermark)",
            f"5. Show top 3 to user (semi-auto), get pick",
            f"6. mcp__nano-banana__edit_image with heavy transformation prompt",
            f"7. Upload to WP, inject, verify",
        ]
    elif args.path == 'C':
        if not args.before_image or not args.after_image:
            print('ERROR: path C requires --before-image and --after-image (real patient photos only)',
                  file=sys.stderr)
            sys.exit(2)
        if not Path(args.before_image).exists() or not Path(args.after_image).exists():
            print('ERROR: image file(s) not found', file=sys.stderr)
            sys.exit(2)
        plan['next_steps'] = [
            f"1. Verify both images are owned by Dr. Meir's clinic (ETHICS).",
            f"2. mcp__claude_ai_higgsfield__media_upload for both",
            f"3. mcp__claude_ai_higgsfield__generate_video model=seedance_2_0 with start/end frames",
            f"4. Poll job_status until terminal (~60-180s)",
            f"5. Download mp4 to {workdir}/output.mp4",
            f"6. Upload to WP media, also extract poster frame",
            f"7. Build figure from templates/video_embed.html",
            f"8. Inject + verify",
        ]

    plan_path = workdir / 'plan.json'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print(f'\n# Plan saved to {plan_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
