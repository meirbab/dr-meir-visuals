---
name: dr-meir-visuals
description: Visual + content enrichment pipeline for dr-meir.com pages. Input is a target post URL plus 1+ Instagram links the user picked manually (no keyword scraping). The skill (1) pulls each IG post via Apify URL mode to get image + caption, (2) cleans every image via Higgsfield nano_banana_2 — removes text/logos/watermarks, replaces the original background with a neutral studio gradient, mild enhancement, (3) builds a deterministic Instagram-reel-style BEFORE/AFTER slider-wipe video with PIL + ffmpeg from the first cleaned image (BEFORE fills frame → vertical slider sweeps right→centre → side-by-side hold with bilingual labels), (4) uploads all media to WP and replaces galleries on the target post (the last gallery becomes the video widget by default), (5) mines the captions for facts, stats and mechanisms NOT yet on the page and injects them as a new science block + FAQ items + heading fixes, (6) clears cache and submits IndexNow. The user can override any step in plain language ("don't change the background", "skip the video", "use Kling morph instead of slider", "place after the recovery section"). Triggers — "/dr-meir-visuals", "enrich post <url> with these IG links", "החלף גלריות בעמוד <url> עם התמונות מהקישורים הבאים", "עדכן את העמוד עם הלינקים <urls>".
---

# dr-meir-visuals — Manual-link Visual & Content Enrichment for dr-meir.com

End-to-end pipeline for enriching a dr-meir.com page with visuals AND text mined from Instagram posts that the **user picked manually**. No more keyword scraping or vision filtering — the user has already done the curation step.

Validated end-to-end on post 52464 (knee liposuction) on 2026-05-05: 3 IG links → 3 cleaned images + 1 PIL/ffmpeg slider-wipe video + α/β-receptor science section + 4 new FAQs + heading fixes, all live. The slider-wipe replaced the v0.3 Kling 3.0 morph attempt because organic AI motion morphs don't reproduce a clean geometric divider sweep — we now build the slider deterministically.

## When to invoke

- "Enrich `<post-url>` with these IG links: `<urls>`"
- "Replace the galleries on `<post-url>` with these Instagram photos"
- "תעדכן את העמוד `<url>` עם הקישורים האלה"
- "/dr-meir-visuals `<post-url>` `<ig1>` `<ig2>` ..."
- Any request that pairs a dr-meir.com page with one or more Instagram links

## When NOT to invoke

- Pages outside dr-meir.com
- Bulk gallery edits without source links
- Stock-photo lookups (use a different workflow)
- AI-generated diagrams from prompt only (use the legacy Path A in v0.2 — see archive)

---

## Inputs

| Arg | Required | Format | Notes |
|-----|----------|--------|-------|
| `target` | yes | URL or post id | The page to enrich |
| `instagram_links` | yes (1+) | `https://www.instagram.com/p/<shortcode>/` | User-curated |
| `brief` | no | natural language | What the user wants the skill to do; defaults below if empty |

### Default brief (when `brief` is empty)

For each image, automatically:
1. Remove all text overlays, logos, watermarks, branding
2. Replace the original background with a clean, uniform neutral studio gradient
3. Apply mild enhancement (sharpness, color balance) without changing anatomy/results

Then **always** build one Instagram-reel-style **slider-wipe** video from the first cleaned image (deterministic PIL+ffmpeg, 4.5s, 1080×1080) — UNLESS the brief says "skip video" or asks for an organic morph.

Then **always** mine the captions for content enrichment (facts, statistics, mechanisms) — UNLESS the brief says "skip text".

---

## Pipeline

### 1. Resolve target post

```python
from wp_client import get_post
post_id = post_id_from_url_or_int(target)
post = get_post(post_id)
elementor_tree = json.loads(post['meta']['_elementor_data'])
```

Identify gallery widget IDs. They will be the replacement targets.

### 2. Fetch IG posts via Apify URL mode

`scripts/apify_instagram.py` (rewritten v0.3) calls `apify/instagram-scraper` with `directUrls=[...]` and `resultsType=posts`. Returns image URL, full caption, owner, likesCount, location.

```python
from apify_instagram import fetch_posts
items = fetch_posts(['https://www.instagram.com/p/B_Foa3ZlcQ3/', ...])
# Each item: {shortcode, url, image_url, caption, owner, likes, ...}
```

Download every `image_url` to `/tmp/dr-meir-visuals/<run_id>/raw/<shortcode>.jpg`.

### 3. Pre-flight NSFW guard (Higgsfield)

Higgsfield's nano_banana_2 rejects images whose top-frame contains buttocks, underwear close-ups, or genital area. **Pre-crop the image to mid-thigh-down whenever the IG photo is a full back/front body shot:**

```python
from PIL import Image
im = Image.open(path)
w, h = im.size
# Heuristic: if aspect close to square AND user-described body view, crop top 25-30%
crop = im.crop((0, int(h*0.28), w, int(h*0.88)))
crop.save(path_cropped)
```

Always confirm the upload status — if it returns `nsfw`, retry with a tighter crop or skip that image.

### 4. Upload originals to Higgsfield + run nano_banana_2

```python
from clean_image_higgsfield import clean_one
clean_path = clean_one(
    src_path,
    prompt="...",         # default cleaning prompt — see templates/clean_default.txt
    aspect_ratio="1:1",   # 1:1 for square IG, 16:9 if cropped landscape
    resolution="2k",
)
```

Default prompt template (`templates/clean_default.txt`):

> Edit this medical before/after photo:
>   • COMPLETELY REMOVE every text overlay (Russian/English/Hebrew labels like "ДО", "ПОСЛЕ", BEFORE, AFTER), every logo and every watermark.
>   • REPLACE the original background (clinic floor/wall/IV-stand/tile) with a clean uniform neutral light gray studio gradient.
>   • Keep the patient anatomy, skin tone, pose and the visible BEFORE/AFTER fat-reduction difference EXACTLY as in the original — do NOT alter body shape, do NOT remove or add cellulite/fat.
>   • Slightly enhance overall sharpness and contrast.
>   • Final result: clean clinical before/after photograph on a neutral studio backdrop.

If the user's brief says "no background change" → drop the second bullet. If "no enhancement" → drop the fourth.

Poll `job_status` (sync=true ⇒ ~10-20s per image). Download `rawUrl` to `/tmp/dr-meir-visuals/<run>/clean/img<i>.png`.

### 5. Generate transformation video — slider-wipe (default, deterministic)

The default v0.4 pattern is an **Instagram-reel-style slider wipe**, built deterministically with `PIL + ffmpeg`. The first cleaned BEFORE|AFTER side-by-side image is sliced and animated:

| Phase | Duration | What is shown |
|-------|----------|--------------|
| A     | 1.0s     | Full BEFORE filling the canvas (slider off-screen right) |
| B     | 2.0s     | Vertical white slider (with circular handle + chevrons) sweeps from right edge → centre, smoothstep easing, revealing AFTER on its right |
| C     | 1.5s     | Hold side-by-side BEFORE \| AFTER. Bilingual labels ("לפני" / "אחרי" or "BEFORE" / "AFTER") fade in over 0.4s. |

Total: 4.5s, 30fps, 1080×1080, H.264 + faststart.

```bash
python3 scripts/build_slider_video.py \
    --src /tmp/run/clean/img1.png \
    --out /tmp/run/transformation_slider.mp4 \
    --labels he         # or en / none
```

Or as a library:

```python
from build_slider_video import build
build('/tmp/run/clean/img1.png', '/tmp/run/transformation_slider.mp4', labels='he')
```

**Why deterministic instead of Kling/Seedance morph?** AI video models trained on motion morphs cannot reproduce a clean geometric divider sweep — the line wobbles and the body subtly morphs during the reveal, which is wrong for a clinical comparison. PIL+ffmpeg gives pixel-perfect control, zero AI credits, and the exact Instagram-reel pattern users find familiar.

**Hebrew labels caveat:** PIL has no bidi shaping. The script reverses Hebrew strings before drawing so the visual order is correct.

**Dependencies:** `Pillow` (always installed) and `ffmpeg` (`brew install ffmpeg` on macOS).

### 5b. Alternate: organic Kling 3.0 morph (only if user asks)

If the user explicitly wants an **organic morph** (e.g. "I don't want a slider, I want the body to slim down on camera"), fall back to `scripts/generate_morph_video.py` which prepares start/end frames for Higgsfield Kling 3.0 in `pro` mode, 5s. See `templates/morph_default.txt` for the prompt.

Trigger words for this fallback: "organic morph", "אורגני", "morph the body", "Kling".

If the user's brief says "skip video" → return early with image-only outputs.

### 6. Upload to WP

`scripts/wp_media.py` for each image and the mp4. Hebrew alt/title built from the post's H1 + a sequence number ("לפני ואחרי שאיבת שומן ב<אזור> — תוצאה אמיתית #1").

### 7. Replace galleries on the target post

Default plan when there are 3 image galleries on the page:
- Galleries 1 + 2 → image batches of 3 (cycling the cleaned images)
- Gallery 3 → **video widget** (autoplay, loop, mute, image_overlay = first cleaned image)

If there are fewer galleries — skill fits the available slots and reports what was done.

`scripts/replace_galleries_with_media.py` walks the Elementor tree, finds gallery widgets by `widgetType=='gallery'`, and either replaces `settings.gallery` with new image refs OR replaces the entire widget node with a `widgetType='video'` widget (preserving the original `id` so any custom CSS still binds).

Pattern for the swap-to-video case (validated on 2026-05-05):

```python
{
  'id': original_gallery_id,
  'elType': 'widget',
  'widgetType': 'video',
  'settings': {
    'video_type': 'hosted',
    'hosted_url': {'url': mp4_url, 'source': 'library'},
    'autoplay': 'yes', 'loop': 'yes', 'mute': 'yes', 'play_on_mobile': 'yes',
    'controls': '',
    'image_overlay': {'id': poster_id, 'url': poster_url, 'size': 'full',
                      'alt': '...', 'source': 'library'},
    'show_image_overlay': 'yes',
    'lazy_load': 'yes',
    'aspect_ratio': '11',
  },
  'elements': [],
}
```

### 8. Mine captions → enrichment text

For each caption (Russian / English / Spanish / etc.) extract:

| Signal | Example |
|--------|---------|
| Hard statistic | "46% women report localized fat resistant to diet" |
| Mechanism | "Alpha-2 vs beta receptors", "post-pregnancy hormonal balance" |
| Multi-area combo | "thighs + knees + calves + ankles same session" |
| Recovery details | actual day-by-day timelines from the source |
| Wrong-page-content guards | leftover "סנטר" / "בטן" headings on a knees page |

Then compare against the existing post body. Skill produces:

1. **A new text-editor widget** with a science section in Hebrew, ~400-700 words, using `<h2>`, `<ul>`, `<strong>` — placed just before the FAQ heading.
2. **2-5 new FAQ tabs** appended to the existing toggle widget. Tab title = question, tab_content = `<p>...</p>` answer using new facts only.
3. **Heading fixes**: any leftover keyword from a sister page is replaced (e.g. "דרגת סנטר" → "מבנה הברך") to fix template-clone rot.

Deduplication rule: never inject a fact already present verbatim in the page body. Use Hebrew character n-gram match on H2 titles + first 100 chars of each existing text widget.

Use a **Why:** + **How to apply:** structure for any patient-decision FAQ.

### 9. Push, clear cache, IndexNow

```python
update_elementor(post_id, json.dumps(tree, ensure_ascii=False), clear_css=True)
clear_elementor_cache()  # MANDATORY — see memory: elementor-rest-edit-workflow
submit_indexnow(post['link'])
```

### 10. Verify live

```python
url = post['link'] + '?cb=' + str(int(time.time()))
html = fetch_live_html(url, mobile=False)
assert all(slug in html for slug in expected_slugs)
assert '<video' in html or 'video_widget_id' in html  # only if video step ran
assert science_h2 in html
```

---

## Tools available

| Tool | Purpose |
|------|---------|
| `mcp__claude_ai_higgsfield__media_upload` | Upload originals + morph halves |
| `mcp__claude_ai_higgsfield__media_confirm` | Confirm upload (also surfaces NSFW rejections) |
| `mcp__claude_ai_higgsfield__generate_image` | nano_banana_2 cleaning pass |
| `mcp__claude_ai_higgsfield__generate_video` | kling3_0 / seedance_2_0 morph |
| `mcp__claude_ai_higgsfield__job_status` | Poll (sync=true for short ones) |
| `mcp__claude_ai_higgsfield__models_explore` | Re-discover models if Higgsfield rolls a new one |
| `mcp__nano-banana__edit_image` | Local fallback if a Higgsfield job fails or NSFW persists |
| Bash | Apify URL-mode scrape, curl PUTs, Pillow crop |
| `wp_client.get_post` / `update_elementor` / `clear_elementor_cache` / `submit_indexnow` | Existing infra at `~/.dr-meir/lib/` |

Apify keyword-hashtag scraping from v0.2 is **deprecated** in v0.3 — `scripts/apify_instagram.py` now uses `directUrls` mode only.

---

## Configuration

`~/.dr-meir/credentials.env`:

```
WP_SITE=https://dr-meir.com
WP_USERNAME=<wp-user>
WP_APP_PASSWORD=<app-pass>
APIFY_API_TOKEN=apify_api_...
```

Higgsfield is OAuth via claude.ai Connectors — no key in env.

---

## NSFW handling cookbook

Higgsfield's policy filter rejects:
- Buttocks/glutes close-ups (regardless of clinical context)
- Visible underwear or thongs
- Front-of-pelvis close-ups

When a `media_confirm` returns `status: nsfw`:

1. **First fix**: re-crop the original image to remove the offending region (Pillow), upload again. Top 25-30% crop usually works for back-view shots.
2. **Second fix**: fall back to `mcp__nano-banana__edit_image` (Gemini's policy is more permissive for medical content). Send the original image with the same cleaning prompt.
3. **Last resort**: skip that image and proceed with the remaining set; report that 1 image was excluded.

---

## Caption-mining heuristics (Hebrew enrichment)

When parsing a Russian/English/Spanish caption, only inject content that satisfies ALL three:

1. **Not already on the page** (string-search: facts, percentages, mechanisms)
2. **Verifiable** (mechanism explained in standard endocrinology/derm literature, or framed as "studies suggest" without a fabricated specific citation; never invent a journal name + year + author tuple)
3. **Useful for patient decision-making** (drives understanding of why the procedure exists, not promotional fluff)

Always translate to clinical Hebrew. Avoid the source-clinic's name. Never carry over the source surgeon's branding.

Default insertion point: just before the FAQ heading widget. Default new FAQ count: 2-5 tabs.

If the page has leftover content from a template-clone (e.g. headings still saying "סנטר" on a knee page), fix those headings in the same patch.

---

## Brief grammar — what the user can override

The skill parses the user's free-text brief for these intents:

| User says... | Skill does |
|--------------|-----------|
| "skip video" / "בלי וידאו" | step 5 skipped |
| "skip text" / "בלי טקסט" | step 8 skipped |
| "don't change background" | drops bg-replacement bullet from cleaning prompt |
| "make 2 videos" / "two transformation videos" | runs step 5 twice on different image pairs |
| "place text after <heading>" / "אחרי הכותרת X" | overrides default insertion point |
| "use only image N" | filters image set down to that one |
| "video should be `<duration>`s" | passes through to Kling duration |

Anything not parseable is treated as additional clinical context appended to the cleaning prompt.

---

## File map

```
~/.claude/skills/dr-meir-visuals/
├── SKILL.md                                # this file (v0.3)
├── README.md
├── LICENSE
├── scripts/
│   ├── orchestrate.py                      # v0.3 — IG-links pipeline
│   ├── apify_instagram.py                  # directUrls mode
│   ├── extract_keywords.py                 # used in step 8
│   ├── clean_image_higgsfield.py           # upload + nano_banana_2 + download
│   ├── build_slider_video.py               # v0.4 DEFAULT — PIL+ffmpeg slider-wipe video
│   ├── generate_morph_video.py             # v0.3 alt — Kling 3.0 organic morph (only if asked)
│   ├── mine_captions.py                    # caption → enrichment plan
│   ├── replace_galleries_with_media.py     # generic gallery/video swap
│   ├── wp_media.py                         # upload media to WP
│   └── inject_visual.py                    # insert HTML block into Elementor
├── templates/
│   ├── diagram_overlay.html                # Path-A legacy template
│   ├── video_embed.html                    # video figure (manual mode)
│   ├── clean_default.txt                   # default nano_banana_2 cleaning prompt
│   └── morph_default.txt                   # default kling3_0 morph prompt (alt path)
└── examples/
    ├── post-17924-fat-diagram.md           # v0.1 run notes (anatomical diagram)
    └── post-52464-knee-ig-pipeline.md      # v0.3/v0.4 run notes (IG-link enrichment + slider)
```

---

## Versioning

- **v0.4** (2026-05-05, evening): Slider-wipe video pattern is now the default. Added `scripts/build_slider_video.py` (PIL+ffmpeg) which produces the Instagram-reel-style three-phase wipe (BEFORE fills frame → vertical slider with circular handle sweeps right→centre with smoothstep easing → side-by-side hold with fading bilingual labels). The Kling 3.0 organic morph from v0.3 is now an alternate path (5b in SKILL.md) that fires only when the user asks for "organic morph" / "אורגני" / "Kling". Why: AI motion morphs can't reproduce a clean geometric divider sweep — the line wobbles and the body subtly morphs during the reveal, which is wrong for clinical comparison. Validated on post 52464 — replaced the previous Kling morph with a new slider-wipe mp4 (id 52551).
- **v0.3** (2026-05-05): IG-links input model. Removed keyword-scraping flow. Added cleaning + morph + caption-mining as the default automatic pipeline. Validated end-to-end on post 52464 (knee liposuction): 3 IG links → 3 cleaned images + 1 Kling 3.0 morph video + α/β-receptor science block + 4 new FAQs + 2 heading fixes, all live with IndexNow ping.
- **v0.2** (2026-05-04, evening): Path B validated end-to-end on post 52464. English-first hashtag priority added. Higgsfield `nano_banana_flash` fallback for nano-banana 503s.
- **v0.1** (2026-05-04, morning): Initial — Path A validated end-to-end on post 17924 (subcutaneous-vs-visceral fat diagram).
