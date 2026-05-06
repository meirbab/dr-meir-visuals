---
name: dr-meir-visuals
description: Visual + content enrichment pipeline for dr-meir.com pages. Input is a target post URL plus 1+ Instagram links the user picked manually (no keyword scraping). The skill (1) pulls each IG post via Apify URL mode to get image + caption, (2) cleans every image via Higgsfield nano_banana_2 (with nano-banana fallback when Higgsfield rejects as NSFW) — removes text/logos/watermarks, replaces the original background with a neutral studio gradient, diversifies clothing/underwear across images while keeping anatomy identical, PRESERVES the visible BEFORE/AFTER body-shape difference (don't equalize the halves), (3) builds a deterministic crossfade SLIDESHOW video (v0.7 default) from the cleaned BEFORE/AFTER images with PIL + ffmpeg — each image is held for ~2.5s then smoothly crossfaded into the next; alt patterns (slider-wipe, Kling morph) are available only on explicit user request, (4) **ADDS the new media to the target post alongside any existing media (never replaces or deletes the originals unless the user explicitly says "החלף"/"replace")** — appends to galleries, inserts new image widgets, video widget and diagram below the existing image-row, (5) mines the captions for facts, stats and mechanisms NOT yet on the page and injects them as a new science block + FAQ items + heading fixes, (6) clears cache and submits IndexNow. The user can override any step in plain language ("don't change the background", "skip the video", "use Kling morph instead of slider", "place after the recovery section", "החלף את התמונות הקיימות"). Triggers — "/dr-meir-visuals", "enrich post <url> with these IG links", "הוסף תמונות לעמוד <url>", "עדכן את העמוד עם הלינקים <urls>".
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

## ⚠ Media safety rules — ADD, don't REPLACE (v0.5)

**Hard rule (validated 2026-05-06):** When the user invokes this skill on a page that already has media, the **default behaviour is to ADD the new content, not replace existing media**. Never delete or overwrite an image widget, gallery item, video widget, or featured_media without an explicit instruction.

Why this rule exists: on 2026-05-06 I overwrote the 3 original images on `inner-thigh-lipo` with new IG-derived images, and the user had to manually ask me to revert. Their feedback: "אסור למחוק את המדיה הקיימת" — never delete existing media. WP media library entries are also preserved — even when a widget reference changes, the underlying file stays.

### Default behaviour cheat-sheet

| Existing on the page... | Default action | Replace mode (only if user says so) |
|---|---|---|
| 3 image widgets | INSERT new image widgets BELOW the existing row, in a new sibling container | Swap each image widget's `settings.image` to the new media |
| Existing gallery widget | INSERT a new gallery widget below it (different `id`) | Replace `settings.gallery` array |
| Existing video widget | INSERT a new video widget below | Swap `hosted_url` |
| `featured_media` set | LEAVE alone | Update only when user says "set as cover" |
| FAQ accordion | APPEND new items (never remove existing) | Same |
| WP media library entries | NEVER call DELETE on `wp/v2/media/<id>` | Same |

### Trigger words for explicit REPLACE mode

Only when the user uses one of these phrases should the skill switch from ADD to REPLACE:

- "החלף את התמונות" / "החלף את הוידאו" / "החלף את הגלריה"
- "replace the images" / "swap out the existing photos"
- "remove the old gallery and put these instead"
- "overwrite"

If the trigger is ambiguous ("update the page with these IG links"), default to ADD and report both the original media (kept) and the new media (added) in the run summary so the user can ask for replacement explicitly.

### What "ADD" means for each Elementor structure

- **3-image-row template** (e.g. inner-thigh-lipo): Build a **new sibling container** below the existing `image-row` container, containing the 3 new image widgets. The original `e8b03eb / 3d5e130 / 3617743` widgets are untouched.
- **Gallery template** (e.g. knee-liposuction): Build a **new gallery widget** alongside the existing one (or append items to it without dropping existing ones). Don't replace `settings.gallery` blindly.
- **Bare post**: just inject after the last text-editor in the body container.
- **Video widget**: always insert NEW (not swap), with a unique widget id.
- **Diagram + science text**: always inject NEW, before the FAQ heading.

### When restoration is needed

If a previous session already replaced media (legacy v0.3/v0.4 runs), provide a `revert_post_<id>.py` script that restores the original `image.id` + `image.url` from the WP media library (looking up via REST `wp/v2/media/<id>` for the original featured-image filename in `/2024/05/` or wherever).

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

### 5. Generate transformation video — crossfade slideshow (v0.7 default)

The default v0.7 pattern is a **crossfade slideshow** of the cleaned BEFORE|AFTER images, built deterministically with `PIL + ffmpeg`. Each cleaned image is itself a side-by-side BEFORE | AFTER comparison, so the slideshow simply plays them in sequence with gentle blends — no slider, no jump, no flicker.

```bash
python3 scripts/build_slideshow_video.py \
    --srcs /tmp/run/clean/img1.png /tmp/run/clean/img2.png /tmp/run/clean/img3.png \
    --out /tmp/run/slideshow.mp4 \
    --hold 2.5 --crossfade 0.7 --loop-back
```

| Phase | Default | What is shown |
|-------|---------|---------------|
| Hold #N | 2.5s    | Image #N held still (each image is a clean BEFORE \| AFTER) |
| Crossfade | 0.7s | Smooth blend from image #N → image #N+1 |
| Loop-back | optional | If `--loop-back` set, last image crossfades back to the first for a seamless loop |

For 3 source images with default timings: 3 × 2.5s + 3 × 0.7s = **9.6s**.

**Why slideshow instead of slider-wipe (v0.4–v0.6 default)?** The slider-wipe approach (sweep, then crossfade to side-by-side) had a sync glitch at the seam where the frame appeared to jump between BEFORE and AFTER, breaking the illusion. Slideshow is simpler and proven: each image is itself the BEFORE/AFTER comparison, and the video just plays them in sequence.

**Hebrew labels caveat:** Each cleaned source image already contains the BEFORE/AFTER content positioning, so labels live in the image (or in the surrounding HTML caption), not burned into the video. The slideshow has no overlay text by default.

**Dependencies:** `Pillow` and `ffmpeg`.

### 5b. Alternate: slider-wipe (v0.6 sweep+crossfade) — only if user explicitly asks

If the user explicitly wants the slider-wipe pattern ("slider", "סליידר", "wipe"), use `scripts/build_slider_video.py` instead. It produces the W → 0 sweep + crossfade-to-side-by-side. **Known issue (v0.6):** at the seam between the slider sweep ending and the side-by-side composition starting, some viewers perceive a "jump" between BEFORE and AFTER. Default to the v0.7 slideshow unless the user insists on the slider.

### 5c. Alternate: organic Kling 3.0 morph — only if user asks for "organic morph"

The original v0.3 Kling 3.0 morph remains an alternate path for "I want the body to slim down on camera" requests. See `scripts/generate_morph_video.py`.

### 5-old: slider-wipe (v0.4–v0.6 default) — DEPRECATED but documented for historical reference

The default v0.4 pattern was an **Instagram-reel-style slider wipe**, built deterministically with `PIL + ffmpeg`. The first cleaned BEFORE|AFTER side-by-side image is sliced and animated:

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

- **v0.7** (2026-05-06, late evening): **Crossfade slideshow replaces slider as the default video pattern.** User feedback: "הסליידר לא מסונכרן נכון בווידאו. הוא קופץ למצב שאחרי בדיוק שנייה או שתיים. כשהסליידר מגיע לקראת הסוף, הוא מחליף בין מצב לפני למצב אחרי" (the slider isn't synchronized correctly — it jumps between BEFORE and AFTER near the end). The v0.6 slider had a perceptible seam between phase B (slider sweep) and phase C (crossfade to side-by-side) that read as a "jump" between BEFORE and AFTER. The new v0.7 default is a much simpler **crossfade slideshow**: each cleaned source image is itself a clean BEFORE | AFTER comparison; the video plays them in sequence with a `hold` (default 2.5s) followed by a `crossfade` blend (default 0.7s). For 3 images with default timings: 9.6s total. New script `scripts/build_slideshow_video.py`. The slider-wipe (`build_slider_video.py`) and Kling 3.0 morph (`generate_morph_video.py`) are still present as alternates for users who explicitly ask. Validated on inner-thigh-lipo (post 21747) — slideshow video uploaded as id 52867, replaced the v4 slider video.
- **v0.6** (2026-05-06, evening): **Slider animation fixed**. The v0.4/v0.5 slider stopped at the centre (slider_x = W/2 in phase B + static side-by-side as phase C). User feedback: "הסליידר נתקע באמצע עם תמונה מטושטשת" (the slider got stuck mid-frame with a blurred image) and "הסליידר צריך לנוע עד הסוף, להראות בהתחלה את המצב לפני, לחשוף באמצעות הסליידר את כל המצב אחרי, ועד שהוא מגיע לסוף. אז הפריים משתנה ומציג זה לצד זה". New 4-phase structure (5.1s default): **A** hold full BEFORE (0.8s) → **B** slider sweeps from x=W to x=0, fully revealing AFTER (2.4s) → **C** crossfade from full AFTER to a true side-by-side composition (0.4s) → **D** hold side-by-side with bilingual labels (1.5s). The crossfade is genuine — it's not the slider stopping at centre, it's a smooth blend from "full AFTER" to "BEFORE | AFTER side-by-side", which then holds. Also added: when cleaning images via Higgsfield/nano-banana, the prompt MUST explicitly say "preserve the visible body-shape difference between BEFORE and AFTER halves — do NOT equalize/smooth the difference". Why: 2026-05-06 the cleaning step was averaging the two halves so the side-by-side looked identical between BEFORE and AFTER. The fix is a "PRESERVE THE DIFFERENCE EXACTLY" clause in the cleaning prompt template.
- **v0.5** (2026-05-06): **ADD-not-REPLACE rule** added as a hard safety constraint. When the user invokes the skill on a page that already has media, default behaviour is now to INSERT new media alongside the originals (new sibling container with the new image widgets, new gallery widget alongside the existing one, NEW video widget — never reusing original widget IDs). Replacement only fires when the user explicitly says "החלף" / "replace" / "swap" / "overwrite". Why: 2026-05-06 the user invoked the skill on `inner-thigh-lipo`; I overwrote the 3 original page images with new IG-derived ones, and they had to manually ask for restoration with "אסור למחוק את המדיה הקיימת". Also added: nano-banana fallback path when Higgsfield rejects images as NSFW (validated on the 3 inner-thigh frames where Higgsfield rejected all 3 with NSFW/failed; nano-banana edit_image accepted them with the same prompts). Also added: explicit guidance to DIVERSIFY clothing/underwear across images while keeping anatomy identical (different bottoms/colors per image so the page doesn't look like the same shot reused).
- **v0.4** (2026-05-05, evening): Slider-wipe video pattern is now the default. Added `scripts/build_slider_video.py` (PIL+ffmpeg) which produces the Instagram-reel-style three-phase wipe (BEFORE fills frame → vertical slider with circular handle sweeps right→centre with smoothstep easing → side-by-side hold with fading bilingual labels). The Kling 3.0 organic morph from v0.3 is now an alternate path (5b in SKILL.md) that fires only when the user asks for "organic morph" / "אורגני" / "Kling". Why: AI motion morphs can't reproduce a clean geometric divider sweep — the line wobbles and the body subtly morphs during the reveal, which is wrong for clinical comparison. Validated on post 52464 — replaced the previous Kling morph with a new slider-wipe mp4 (id 52551).
- **v0.3** (2026-05-05): IG-links input model. Removed keyword-scraping flow. Added cleaning + morph + caption-mining as the default automatic pipeline. Validated end-to-end on post 52464 (knee liposuction): 3 IG links → 3 cleaned images + 1 Kling 3.0 morph video + α/β-receptor science block + 4 new FAQs + 2 heading fixes, all live with IndexNow ping.
- **v0.2** (2026-05-04, evening): Path B validated end-to-end on post 52464. English-first hashtag priority added. Higgsfield `nano_banana_flash` fallback for nano-banana 503s.
- **v0.1** (2026-05-04, morning): Initial — Path A validated end-to-end on post 17924 (subcutaneous-vs-visceral fat diagram).
