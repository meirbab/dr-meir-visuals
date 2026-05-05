# Post 52464 — Knee liposuction (v0.3 IG-link enrichment)

Validated end-to-end on 2026-05-05.

## Inputs

- **Target:** `https://dr-meir.com/liposuction/knee-liposuction/` (post id 52464)
- **IG links** (manually curated by user):
  - `https://www.instagram.com/p/B_Foa3ZlcQ3/` (drmalkarov, RU caption with 46% statistic + α/β receptor mechanism)
  - `https://www.instagram.com/p/CAzblOKFzNT/` (300expertov / Эстет Клиник, RU caption with multi-area combo concept)
  - `https://www.instagram.com/p/BhZO5pNnb8e/` (chavdarov.samir73, short RU caption)
- **Brief:** none (default automatic mode)

## Outputs

### 1. Cleaned images (Higgsfield nano_banana_2 @ 2k)

| WP id | URL | Notes |
|-------|-----|-------|
| 52546 | `/wp-content/uploads/2026/05/knee-real-ba-1.png` | Full-leg front view, "300 экспертов" + ДО/ПОСЛЕ removed, neutral gray bg |
| 52547 | `/wp-content/uploads/2026/05/knee-real-ba-2-scaled.png` | Back view, mid-thigh-down crop (NSFW guard), "Doctor Malkarov" branding removed |
| 52548 | `/wp-content/uploads/2026/05/knee-real-ba-3-scaled.png` | Knee close-up, neutral gradient bg |

### 2. Transformation video (Kling 3.0 pro, 5s)

| WP id | URL | Notes |
|-------|-----|-------|
| 52549 | `/wp-content/uploads/2026/05/knee-transformation-morph.mp4` | Slow morph of left half (BEFORE) → right half (AFTER) of img1, 5s, autoplay+loop+muted |

### 3. Gallery + widget plan (Elementor)

| Widget id | Was | Now |
|-----------|-----|-----|
| `dc9fd61` | gallery (3 chin images) | gallery (img1, img2, img3) |
| `b6a0abb` | gallery (3 chin images) | gallery (img3, img1, img2) |
| `4290ce8` | gallery (3 chin images) | **video widget** (mp4, autoplay, poster=img1) |

### 4. Caption mining → injected text

A new text-editor widget was inserted just before the FAQ heading:

> **H2: מדוע שומן בברכיים עמיד בפני דיאטה?**
>
> Hebrew explanation of α2/β adrenergic receptor profile on adipocytes (mined
> from drmalkarov caption). Cites the Lafontan endocrinology research on
> α2:β receptor ratios in galife/inner-thigh fat. Includes the 46% statistic
> from the source caption.

4 new FAQ tabs were appended to the existing toggle:

1. "האם דיאטה ופעילות גופנית יכולות להסיר שומן מאזור הברך?" — answer cites α2 receptor blockage (mined from caption #1)
2. "האם אפשר לשלב שאיבה בברכיים עם שאיבה באזורים נוספים?" — multi-area combo (mined from caption #2)
3. "מה ההבדל בין שאיבה לאחר הריון לבין נשים שלא ילדו?" — original synthesis
4. "האם שאיבת לייזר מתאימה לאזור הברך?" — original synthesis

2 leftover headings from a sister-page template were fixed:
- "התאמת הטיפול לדרגת סנטר" → "התאמת הטיפול למבנה הברך"
- "שאלות נפוצות אודות שאיבת שומן מהסנטר" → "שאלות נפוצות אודות שאיבת שומן בברכיים"

## Lessons learned (added to v0.3)

1. **NSFW filter on back-of-body shots** — Higgsfield rejected the back-view leg photo on first upload (visible underwear). Fix: Pillow crop top 28-30% + bottom 12% before upload. SKILL documents this as a default for portrait/back-view inputs.
2. **Apify directUrls mode** is faster + more reliable than hashtag scraping for user-curated inputs. The first call returns image URL + full caption; no follow-up scoring loop needed.
3. **Caption mining is high-value content**. Russian captions from working clinicians often contain mechanism explanations and statistics that competing Hebrew pages lack. Translating + de-branding produces unique, citable content.
4. **Always check for leftover keywords from sister-page templates** in the same patch. The knee post was cloned from a chin-liposuction template; 2 headings still mentioned "סנטר".

## Verification

- 9/9 expected slugs in live HTML
- `<video>` tag present with autoplay+loop+muted
- α/β receptor terms + 46% stat + Lafontan reference all rendered
- Toggle tab count went from 5 → 9
- Old chin gallery URLs gone (verified via grep on rendered HTML)
- IndexNow ack: 1 URL submitted

---

## v0.4 update (2026-05-05 evening) — slider video replaces Kling morph

After the v0.3 Kling 3.0 morph went live, the user reported it looked "weird" — the body subtly morphed during the reveal, breaking the clinical-comparison illusion. They asked for the Instagram-reel-style slider-wipe pattern instead (`https://www.instagram.com/reel/DX9eXdjg2uH/`).

Built `scripts/build_slider_video.py` (PIL+ffmpeg), regenerated the video from the same `img1` source, and swapped the existing video widget on post 52464:

| | v0.3 (Kling 3.0) | v0.4 (slider-wipe) |
|---|---|---|
| Tool | Higgsfield Kling 3.0, pro mode | PIL + ffmpeg, deterministic |
| Duration | 5s | 4.5s (1.0 + 2.0 + 1.5) |
| Pattern | Smooth motion morph | BEFORE → vertical slider sweeps right→centre → side-by-side hold |
| Labels | None | לפני / אחרי, fade in over 0.4s |
| Anatomy artifacts | Subtle morphing during reveal | None — geometric mask, anatomy stays pixel-perfect |
| AI credit cost | 1 Kling pro video | 0 |
| WP media id | 52549 (replaced) | **52551** (current) |
| URL | knee-transformation-morph.mp4 (gone) | knee-before-after-slider.mp4 (live) |

**Lesson learned (added to v0.4 SKILL.md):** AI video models trained on motion morphs cannot reproduce a clean geometric divider sweep. For clinical before/after comparisons, deterministic PIL+ffmpeg is the right tool. Kling/Seedance now sits behind a "morph" trigger word for the rare cases when an organic on-camera transformation is genuinely wanted.
