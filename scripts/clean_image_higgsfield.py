#!/usr/bin/env python3
"""
clean_image_higgsfield.py — single-image cleaning helper for v0.3.

What it does (no MCP calls — Claude orchestrates those):
  1. Detects whether a Pillow pre-crop is recommended (likely-NSFW header).
  2. Returns a structured plan dict with: src path, recommended crop bbox,
     prompt to feed to nano_banana_2, expected aspect_ratio + resolution.
  3. After Claude has called media_upload + media_confirm + generate_image
     and downloaded the result, this script's `register_clean(...)` helper
     records the (src, clean_path) mapping so downstream steps can re-find it.

Use Pillow if available — otherwise return the original bbox and let Claude
decide whether to crop manually.
"""
import argparse
import json
import sys
from pathlib import Path

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / 'templates' / 'clean_default.txt'
)


def load_default_prompt():
    if DEFAULT_PROMPT_PATH.exists():
        text = DEFAULT_PROMPT_PATH.read_text(encoding='utf-8').strip()
        # Drop the override-hints block from the prompt sent to the model
        text = text.split('\nOverride hints')[0].rstrip()
        return text
    return (
        'Edit this medical before/after photo: remove text/logos/watermarks, '
        'replace background with a neutral light gray studio gradient, '
        'keep anatomy and skin tone exactly as in the original, '
        'slightly enhance overall sharpness.'
    )


def maybe_crop(src_path: str, body_view_hint: str = 'auto'):
    """Return crop bbox + path if a top-crop is needed for NSFW guard.

    body_view_hint:
      - 'auto'        — crop only if image height > width (portrait)
      - 'force'       — always crop top 28%
      - 'no'          — never crop
    """
    try:
        from PIL import Image
    except ImportError:
        return None, None
    src = Path(src_path)
    if not src.exists():
        return None, None
    im = Image.open(src)
    w, h = im.size
    if body_view_hint == 'no':
        return None, None
    if body_view_hint == 'force' or (body_view_hint == 'auto' and h > w):
        top = int(h * 0.28)
        bottom = int(h * 0.88)
        crop = im.crop((0, top, w, bottom))
        out = src.with_name(src.stem + '_crop.jpg')
        crop.save(out, quality=92)
        return (0, top, w, bottom), str(out)
    return None, None


def split_for_morph(src_path: str, out_dir: str = None):
    """Split a square before/after image into BEFORE half + AFTER half.

    Returns dict with 'before_path' and 'after_path'. Each is padded to 1024x1024
    so Higgsfield gets a clean square input for Kling 3.0.
    """
    from PIL import Image
    src = Path(src_path)
    out_dir = Path(out_dir) if out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
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

    before_p = out_dir / f'{src.stem}_before.png'
    after_p = out_dir / f'{src.stem}_after.png'
    fit_square(left).save(before_p)
    fit_square(right).save(after_p)
    return {'before_path': str(before_p), 'after_path': str(after_p)}


def build_clean_plan(src_path: str, brief: str = '', body_view_hint: str = 'auto'):
    base = load_default_prompt()
    extras = []
    brief_lower = (brief or '').lower()
    if 'no background change' in brief_lower or 'בלי שינוי רקע' in (brief or ''):
        extras.append('NOTE: KEEP the original background as-is, do not replace it.')
    if 'no enhancement' in brief_lower or 'בלי שיפור' in (brief or ''):
        extras.append('NOTE: Do not apply sharpness or contrast enhancement.')
    if 'keep watermarks' in brief_lower:
        extras.append('NOTE: Keep visible watermarks/logos as-is.')
    full_prompt = base + ('\n' + '\n'.join(extras) if extras else '')

    crop_bbox, cropped = maybe_crop(src_path, body_view_hint)
    return {
        'src_path': src_path,
        'crop_bbox': crop_bbox,
        'cropped_path': cropped,
        'higgsfield_model': 'nano_banana_2',
        'aspect_ratio': '1:1' if not crop_bbox else '16:9',
        'resolution': '2k',
        'prompt': full_prompt,
        'media_role': 'image',
    }


def register_clean(run_dir: str, src_path: str, clean_path: str):
    rd = Path(run_dir)
    rd.mkdir(parents=True, exist_ok=True)
    log = rd / 'cleaned.jsonl'
    entry = {'src': src_path, 'clean': clean_path}
    with log.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['plan', 'split', 'register'])
    ap.add_argument('--src', required=True)
    ap.add_argument('--brief', default='')
    ap.add_argument('--body-view-hint', default='auto', choices=['auto', 'force', 'no'])
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--clean-path', default=None)
    ap.add_argument('--run-dir', default=None)
    args = ap.parse_args()

    if args.cmd == 'plan':
        plan = build_clean_plan(args.src, args.brief, args.body_view_hint)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif args.cmd == 'split':
        if args.out_dir is None:
            print('--out-dir required for split', file=sys.stderr)
            sys.exit(2)
        out = split_for_morph(args.src, args.out_dir)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == 'register':
        if not args.clean_path or not args.run_dir:
            print('--clean-path and --run-dir required for register', file=sys.stderr)
            sys.exit(2)
        register_clean(args.run_dir, args.src, args.clean_path)
        print('ok')


if __name__ == '__main__':
    main()
