#!/usr/bin/env python3
"""
generate_morph_video.py — produce the start_image / end_image pair for a
Higgsfield Kling 3.0 transformation video.

Claude orchestrates the actual MCP calls (media_upload + media_confirm +
generate_video + job_status). This script just prepares inputs and the
final embed HTML.

Inputs (CLI):
    python3 generate_morph_video.py prepare --src CLEAN_BA_PATH --out-dir DIR

Output JSON:
    {
      "before_path": ".../before.png",
      "after_path":  ".../after.png",
      "video_model": "kling3_0",
      "video_mode":  "pro",
      "duration":    5,
      "aspect_ratio":"1:1",
      "prompt":      "..."   (from templates/morph_default.txt)
    }

After Claude has the mp4, build the embed HTML with `embed`:

    python3 generate_morph_video.py embed --video-url URL --poster-url URL \\
        --alt 'תיאור עברית' --out /tmp/run/video_embed.html
"""
import argparse
import json
from pathlib import Path

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / 'templates' / 'morph_default.txt'
)


def load_default_morph_prompt():
    if DEFAULT_PROMPT_PATH.exists():
        text = DEFAULT_PROMPT_PATH.read_text(encoding='utf-8').strip()
        text = text.split('\nOverride hints')[0].rstrip()
        return text
    return (
        'Slow smooth medical-grade transformation: the body area gradually becomes '
        'slimmer and more sculpted. Excess fat reduces, contour tightens. '
        'Pose and camera completely static. Soft clinical studio lighting.'
    )


def prepare(src_path: str, out_dir: str, brief: str = ''):
    from PIL import Image
    src = Path(src_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    im = Image.open(src)
    w, h = im.size
    mid = w // 2
    left = im.crop((0, 0, max(mid - 8, 1), h))
    right = im.crop((min(mid + 8, w - 1), 0, w, h))

    def fit_square(img, size=1024, bg=(245, 245, 245)):
        ratio = size / max(img.size)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        scaled = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new('RGB', (size, size), bg)
        canvas.paste(scaled, ((size - new_w) // 2, (size - new_h) // 2))
        return canvas

    before_p = out / f'{src.stem}_before.png'
    after_p = out / f'{src.stem}_after.png'
    fit_square(left).save(before_p)
    fit_square(right).save(after_p)

    prompt = load_default_morph_prompt()
    if 'fast morph' in brief.lower():
        prompt += ' Transformation should happen smoothly across the full duration with a clear final state.'
    if 'single area' in brief.lower():
        prompt = prompt.replace('the body area', 'the targeted area only — surrounding regions stay identical')

    return {
        'before_path': str(before_p),
        'after_path': str(after_p),
        'video_model': 'kling3_0',
        'video_mode': 'pro',
        'duration': 5,
        'aspect_ratio': '1:1',
        'prompt': prompt,
        'fallback_model': 'seedance_2_0',
    }


VIDEO_EMBED_TPL = '''<figure style="margin:2em auto;max-width:680px;text-align:center">
  <video controls preload="metadata" autoplay loop muted playsinline poster="{poster_url}" style="width:100%;border-radius:12px;background:#fafafa;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
    <source src="{video_url}" type="video/mp4">
    הדפדפן שלך אינו תומך בנגן הווידאו.
  </video>
  <figcaption style="font-size:0.9em;color:#666;margin-top:10px;font-style:italic">{alt}</figcaption>
</figure>
'''


def embed(video_url: str, poster_url: str, alt: str = 'סרטון טרנספורמציה — לפני ואחרי'):
    return VIDEO_EMBED_TPL.format(video_url=video_url, poster_url=poster_url, alt=alt)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('prepare')
    p.add_argument('--src', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--brief', default='')

    e = sub.add_parser('embed')
    e.add_argument('--video-url', required=True)
    e.add_argument('--poster-url', required=True)
    e.add_argument('--alt', default='סרטון טרנספורמציה — לפני ואחרי')
    e.add_argument('--out', required=True)

    args = ap.parse_args()
    if args.cmd == 'prepare':
        out = prepare(args.src, args.out_dir, args.brief)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == 'embed':
        html = embed(args.video_url, args.poster_url, args.alt)
        Path(args.out).write_text(html, encoding='utf-8')
        print(args.out)


if __name__ == '__main__':
    main()
