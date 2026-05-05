#!/usr/bin/env python3
"""
build_slider_video.py — Default v0.4 BEFORE/AFTER slider-wipe video.

Builds the Instagram-reel-style slider video deterministically with PIL +
ffmpeg, given a side-by-side BEFORE|AFTER image (typically the output of
clean_image_higgsfield.py).

Pattern:
    Phase A — full BEFORE filling the canvas
    Phase B — vertical slider (with handle) sweeps from right edge to centre,
              revealing AFTER on its right
    Phase C — hold side-by-side, with bilingual labels fading in

Why deterministic and not Kling 3.0?
- Kling/Seedance produce smooth motion morphs and don't reproduce a clean
  geometric slider wipe — the divider line wobbles or the body subtly morphs
  during the reveal, which is wrong for a clinical comparison video.
- PIL + ffmpeg gives pixel-perfect control, zero AI credit cost, deterministic
  output, and matches the Instagram-reel pattern users find familiar.

Usage as CLI:
    python3 build_slider_video.py \\
        --src /tmp/run/clean/img1.png \\
        --out /tmp/run/transformation_slider.mp4 \\
        [--width 1080 --height 1080 --fps 30] \\
        [--phase-a 1.0 --phase-b 2.0 --phase-c 1.5] \\
        [--labels lang=he]      # he / en / none

Usage as library:
    from build_slider_video import build
    out = build('/path/to/img1.png', '/tmp/out.mp4', labels='he')
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _find_font(size):
    candidates = [
        '/System/Library/Fonts/SFHebrew.ttf',
        '/System/Library/Fonts/SFHebrewRounded.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _fit(im, w, h):
    src_w, src_h = im.size
    scale = max(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    im_r = im.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 2
    return im_r.crop((x, y, x + w, y + h))


def _label_text(lang):
    if lang == 'he':
        # PIL has no bidi shaping, so reverse Hebrew strings for visual order.
        return ('לפני'[::-1], 'אחרי'[::-1])
    if lang == 'en':
        return ('BEFORE', 'AFTER')
    return (None, None)


def _stamp_label(rgba, text, cx, cy, alpha, font):
    if text is None or alpha <= 0:
        return
    d = ImageDraw.Draw(rgba)
    pad_x, pad_y = 26, 14
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    bx0 = cx - tw // 2 - pad_x
    by0 = cy - th // 2 - pad_y
    bx1 = cx + tw // 2 + pad_x
    by1 = cy + th // 2 + pad_y
    ov = Image.new('RGBA', (bx1 - bx0, by1 - by0), (0, 0, 0, int(alpha * 0.6)))
    rgba.paste(ov, (bx0, by0), ov)
    d2 = ImageDraw.Draw(rgba)
    d2.text(
        (cx - tw // 2 - bbox[0], cy - th // 2 - bbox[1]),
        text,
        font=font,
        fill=(255, 255, 255, alpha),
    )


def build(src_path, out_path, width=1080, height=1080, fps=30,
          phase_a=1.0, phase_b=2.0, phase_c=1.5, labels='he',
          frames_dir=None):
    """Build the slider-wipe video. Returns the output mp4 path."""
    src = Path(src_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if frames_dir is None:
        frames_dir = out.parent / (out.stem + '_frames')
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob('*.png'):
        f.unlink()

    img1 = Image.open(src).convert('RGB')
    W, H = img1.size
    mid = W // 2
    before_half = img1.crop((0, 0, mid, H))
    after_half = img1.crop((mid, 0, W, H))

    before_full = _fit(before_half, width, height)
    after_full = _fit(after_half, width, height)

    font_lbl = _find_font(54)
    left_text, right_text = _label_text(labels)

    total = phase_a + phase_b + phase_c
    n_frames = int(total * fps)

    for i in range(n_frames):
        t = i / fps
        if t < phase_a:
            slider_x = width
            show_line = False
            label_alpha = 0
        elif t < phase_a + phase_b:
            progress = (t - phase_a) / phase_b
            smooth = progress * progress * (3 - 2 * progress)  # smoothstep
            slider_x = int(width - smooth * (width / 2))
            show_line = True
            label_alpha = 0
        else:
            slider_x = width // 2
            show_line = True
            fade = min(1.0, (t - phase_a - phase_b) / 0.4)
            label_alpha = int(fade * 255)

        canvas = before_full.copy()
        if slider_x < width:
            right = after_full.crop((slider_x, 0, width, height))
            canvas.paste(right, (slider_x, 0))
        rgba = canvas.convert('RGBA')

        if show_line and 0 <= slider_x <= width:
            d = ImageDraw.Draw(rgba)
            line_w = 5
            d.rectangle(
                (slider_x - line_w // 2, 0, slider_x + line_w // 2, height),
                fill=(255, 255, 255, 240),
            )
            cx, cy = slider_x, height // 2
            r = 36
            d.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                fill=(255, 255, 255, 235),
                outline=(220, 220, 220, 255),
                width=2,
            )
            chev_w = 12
            d.polygon(
                [(cx - chev_w, cy), (cx - 2, cy - 12), (cx - 2, cy + 12)],
                fill=(120, 120, 120, 255),
            )
            d.polygon(
                [(cx + chev_w, cy), (cx + 2, cy - 12), (cx + 2, cy + 12)],
                fill=(120, 120, 120, 255),
            )

        _stamp_label(rgba, left_text, width // 4, height - 80, label_alpha, font_lbl)
        _stamp_label(rgba, right_text, 3 * width // 4, height - 80, label_alpha, font_lbl)

        rgba.convert('RGB').save(frames_dir / f'f_{i:04d}.png')

    cmd = [
        'ffmpeg', '-y',
        '-framerate', str(fps),
        '-i', str(frames_dir / 'f_%04d.png'),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '20',
        '-preset', 'medium',
        '-movflags', '+faststart',
        str(out),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        sys.stderr.write(res.stderr.decode('utf-8', errors='ignore'))
        raise RuntimeError(f'ffmpeg failed (exit {res.returncode})')

    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='Cleaned BEFORE|AFTER side-by-side image')
    ap.add_argument('--out', required=True, help='Output mp4 path')
    ap.add_argument('--width', type=int, default=1080)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--phase-a', type=float, default=1.0)
    ap.add_argument('--phase-b', type=float, default=2.0)
    ap.add_argument('--phase-c', type=float, default=1.5)
    ap.add_argument('--labels', choices=['he', 'en', 'none'], default='he')
    ap.add_argument('--frames-dir', default=None)
    args = ap.parse_args()

    path = build(
        src_path=args.src,
        out_path=args.out,
        width=args.width,
        height=args.height,
        fps=args.fps,
        phase_a=args.phase_a,
        phase_b=args.phase_b,
        phase_c=args.phase_c,
        labels=args.labels,
        frames_dir=args.frames_dir,
    )
    size = Path(path).stat().st_size // 1024
    duration = args.phase_a + args.phase_b + args.phase_c
    print(f'{path}  ({size} KB, {duration}s @ {args.fps}fps)')


if __name__ == '__main__':
    main()
