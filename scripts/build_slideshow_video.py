#!/usr/bin/env python3
"""
build_slideshow_video.py — v0.7 DEFAULT BEFORE/AFTER slideshow video.

Plays a sequence of already-cleaned BEFORE/AFTER images with smooth crossfade
transitions between them. Each image is held for `hold` seconds, then a
`crossfade` second blend transitions to the next image. The sequence loops
naturally (last image crossfades back to the first only if requested).

Why slideshow instead of slider-wipe (the v0.4-v0.6 default):
    User feedback (2026-05-06): the slider-wipe approach had a sync glitch at
    the end of the sweep where the frame "jumped" between BEFORE and AFTER,
    breaking the illusion. The slideshow pattern is much simpler:
    each image is itself a clean BEFORE | AFTER comparison, and the video just
    plays them in sequence with gentle blends. No slider, no jump, no flicker.

Inputs (CLI):
    python3 build_slideshow_video.py \\
        --srcs /path/img1.png /path/img2.png /path/img3.png \\
        --out /tmp/run/slideshow.mp4 \\
        [--width 1080 --height 1080 --fps 30] \\
        [--hold 2.5 --crossfade 0.7] \\
        [--loop-back]   # if set, last image crossfades back to first for seamless loop

Or as a library:
    from build_slideshow_video import build
    build([img1, img2, img3], '/tmp/out.mp4')
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _fit(im, w, h, bg=(245, 245, 245)):
    """Fit image into wxh (cover, then center-crop to exact)."""
    src_w, src_h = im.size
    scale = max(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    im_r = im.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 2
    return im_r.crop((x, y, x + w, y + h))


def build(src_paths, out_path, width=1080, height=1080, fps=30,
          hold=2.5, crossfade=0.7, loop_back=False, frames_dir=None):
    """Build the slideshow video. Returns the output mp4 path."""
    if not src_paths:
        raise ValueError('Need at least 1 source image')
    src_paths = [str(Path(p)) for p in src_paths]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if frames_dir is None:
        frames_dir = out.parent / (out.stem + '_frames')
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob('*.png'):
        f.unlink()

    images = [_fit(Image.open(p).convert('RGB'), width, height) for p in src_paths]
    n = len(images)

    # Total = n holds + (n-1 crossfades) + (loop_back ? 1 crossfade : 0)
    n_crossfades = n if loop_back else (n - 1)
    total = n * hold + n_crossfades * crossfade
    n_frames = max(1, int(total * fps))

    # Cycle length when looping all the way around (used only if loop_back)
    full_cycle = total

    for i in range(n_frames):
        t = i / fps

        # Walk the timeline to find current segment
        cursor = 0.0
        frame = None
        for seg_idx in range(n + (1 if loop_back else 0)):
            # If at last and not loop_back, only n-1 crossfades follow holds
            is_last_image = (seg_idx == n - 1)
            seg_hold_end = cursor + hold
            if t < seg_hold_end:
                # Inside the hold of image[seg_idx]
                frame = images[seg_idx % n]
                break
            if not loop_back and is_last_image:
                # Final hold: clamp to last image
                frame = images[-1]
                break
            seg_cf_end = seg_hold_end + crossfade
            if t < seg_cf_end:
                # Inside crossfade from images[seg_idx] -> images[(seg_idx+1) % n]
                alpha = (t - seg_hold_end) / crossfade
                a = images[seg_idx % n]
                b = images[(seg_idx + 1) % n]
                frame = Image.blend(a, b, alpha)
                break
            cursor = seg_cf_end
        else:
            # Past end (only happens with loop_back when t > total): wrap
            frame = images[0]

        frame.save(frames_dir / f'f_{i:04d}.png')

    # Compile with ffmpeg
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
    ap.add_argument('--srcs', nargs='+', required=True,
                    help='2+ source images (already cleaned, each a BEFORE|AFTER comparison)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--width', type=int, default=1080)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--hold', type=float, default=2.5,
                    help='Seconds each image is held still')
    ap.add_argument('--crossfade', type=float, default=0.7,
                    help='Seconds for the blend between consecutive images')
    ap.add_argument('--loop-back', action='store_true',
                    help='If set, last image crossfades back to the first (seamless loop)')
    ap.add_argument('--frames-dir', default=None)
    args = ap.parse_args()

    path = build(
        src_paths=args.srcs,
        out_path=args.out,
        width=args.width,
        height=args.height,
        fps=args.fps,
        hold=args.hold,
        crossfade=args.crossfade,
        loop_back=args.loop_back,
        frames_dir=args.frames_dir,
    )
    size = Path(path).stat().st_size // 1024
    n = len(args.srcs)
    n_cf = n if args.loop_back else (n - 1)
    duration = n * args.hold + n_cf * args.crossfade
    print(f'{path}  ({size} KB, {duration}s @ {args.fps}fps, {n} images)')


if __name__ == '__main__':
    main()
