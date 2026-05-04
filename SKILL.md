---
name: dr-meir-visuals
description: AI visual enrichment pipeline for dr-meir.com pages. Extracts Hebrew keywords from a WordPress post, translates to Russian, scrapes Instagram via Apify for inspiration, filters images via vision analysis, then generates either (A) anatomical diagrams via nano-banana with Hebrew HTML overlay labels, (B) AI-transformed images via nano-banana edit, or (C) image-to-video transformations via Higgsfield, and injects the final visual into the page at the right semantic location with cache flush + IndexNow ping. Triggers — "enrich this page with AI visual", "create diagram for post X", "generate before/after video for X", "add visual to dr-meir post Y", "/dr-meir-visuals", or any request to add AI-generated images/videos to dr-meir.com posts.
---

# dr-meir-visuals — AI Visual Enrichment for dr-meir.com

End-to-end pipeline for enriching dr-meir.com Hebrew medical/aesthetic pages with AI-generated visuals. Validated on post 17924 (abdominal liposuction) on 2026-05-04 — generated subcutaneous-vs-visceral fat anatomical diagram with Hebrew HTML overlay labels, injected at the right semantic location, all pages live and mobile-safe.

## When to invoke

- "Enrich post X with AI visual"
- "Create a diagram for the abdominal page"
- "Add anatomical illustration to chin liposuction post"
- "Generate before/after video for thigh page" (path C, requires real patient photos)
- "Add visual to https://dr-meir.com/liposuction/..."
- "/dr-meir-visuals <post_id> <path>"
- Any request that involves adding AI-generated images, diagrams, or videos to a dr-meir.com post

## When NOT to invoke

- Generic "create an image" without a dr-meir.com target page
- Pages outside dr-meir.com
- Stock-photo lookups without AI transformation
- Bulk image gallery uploads (use the WP admin)

---

## The 3 visual paths

| Path | Output | When to use | Tools |
|------|--------|-------------|-------|
| **A — Diagram** | Static anatomical/explainer diagram with Hebrew HTML overlay labels | When the section explains a concept (anatomy, comparison, cause-effect) | nano-banana `generate_image` + custom HTML overlay |
| **B — Transformed image** | AI-modified concept/lifestyle image (background swap, style transfer) | When the section needs a generic visual (clinic shot, mood, technology hero) | Apify Instagram → nano-banana `edit_image` |
| **C — Image-to-video** | Short cinematic video (transformation, motion, parallax) | Before/after morphs, technology demos, hero animations | Real before/after images → Higgsfield `generate_video` |

**ETHICS RULE — Path C only with real authenticated patient photos.** Never use scraped before/after images for medical results — Israeli medical-board ethics violation. Path C is reserved for transformations where the source images are owned by Dr. Meir's clinic.

---

## Pipeline — step by step

### 1. Fetch & analyze the target page

```python
# Use ~/.dr-meir/lib/wp_client.py
from wp_client import get_post
post = get_post(post_id)
```

Extract:
- `H1` → primary keyword
- All `H2` → section topics
- Rank Math `focus_keyword` (in `meta`)
- All `<p>` text in body widgets → context

### 2. Identify the injection point

Walk the Elementor tree (`~/.dr-meir/lib/elementor_tree.py` or pattern in `inject_fat_diagram.py`). Find the text-editor widget whose `editor` field contains keywords matching the user's request topic.

The visual will be inserted RIGHT AFTER that section's primary `</h2>` or `</ol>`.

### 3. Decide the path

If the user said "diagram" / "תרשים" / "infographic" / "illustration explaining" → **Path A**.
If the user said "image" / "תמונה" / "concept photo" / "background" → **Path B**.
If the user said "video" / "וידאו" / "before/after morph" / "transformation" → **Path C**.
If unclear → ask the user.

### 4. Path A — generate diagram (nano-banana, no scrape needed)

```python
# scripts/generate_diagram.py
mcp__nano-banana__generate_image(prompt=clinical_diagram_prompt)
# → /Users/meirbabaev/generated_imgs/generated-*.png
```

**Critical Hebrew-text caveat:** Gemini cannot render Hebrew correctly inside generated images. Always:
1. Generate WITHOUT text labels (clean anatomy/concept only)
2. Use `mcp__nano-banana__edit_image` with prompt "Remove ALL text labels…" if the first pass had any English text
3. Add Hebrew labels via the HTML wrapper in `templates/diagram_overlay.py`

The HTML overlay pattern (validated v3):

```html
<figure style="margin:2em auto;max-width:960px;background:#fafafa;border-radius:14px;padding:28px;box-shadow:0 2px 10px rgba(0,0,0,0.06);text-align:center">
  <h3>{title_hebrew}</h3>
  <div style="display:flex;justify-content:center;align-items:center;gap:24px;flex-wrap:wrap">
    <div style="flex:1 1 380px;min-width:300px;max-width:540px">
      <img src="{IMAGE_URL}" alt="{alt_text}" style="width:100%;border-radius:10px" loading="lazy" decoding="async" />
    </div>
    <div style="flex:1 1 260px;min-width:240px;max-width:340px;text-align:right">
      <ol style="list-style:none;padding:0;margin:0">
        {labeled_items}
      </ol>
    </div>
  </div>
  <figcaption>תרשים: ד"ר מאיר באבאיב — קליניקה לרפואת עור ואסתטיקה, תל אביב</figcaption>
</figure>
```

Image proportion: ~60% width on desktop, stacks on mobile via `flex-wrap`. Image max-width 540px, label box max-width 340px. **This proportion was validated on 2026-05-04 — image looks dominant, labels readable.**

### 5. Path B — Apify scrape + nano-banana edit

```python
# scripts/apify_instagram.py
# Run apify/instagram-hashtag-scraper for translated keyword
import urllib.request, json, os
APIFY_TOKEN = os.environ['APIFY_API_TOKEN']
url = f'https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}'
payload = {'hashtags': [translated_kw], 'resultsLimit': 30}
results = ...  # POST + parse JSON
```

Filter results:
- Type=image only (skip video/carousel)
- Engagement >= 50 likes
- Image dimensions >= 800x800
- Drop carousels with text overlays / ads

Vision-score top 20 candidates by reading each image:
- relevance to topic (0-10)
- quality (0-10)
- style fit for medical site (clinical/aesthetic vs lifestyle/inappropriate)
- watermark/logo presence

Top 3 → user selects one (option 2 — semi-auto). Then:

```python
mcp__nano-banana__edit_image(
  imagePath=downloaded_path,
  prompt='Heavy AI transformation: change background to clinical setting, '
         'remove watermarks/logos, blur identifying features, '
         'apply professional medical photography style.'
)
```

Goal: transform deeply enough that reverse-image-search won't link to source.

### 6. Path C — Higgsfield image-to-video

**Only with user-owned before/after pair:**

```python
# Upload both images
mcp__claude_ai_higgsfield__media_upload(...)
# Generate the transition
mcp__claude_ai_higgsfield__generate_video(params={
  'model': 'seedance_2_0',  # or 'kling3_0' for multi-shot
  'prompt': 'Smooth medical-grade morph from before to after, professional clinical lighting',
  'medias': [
    {'value': before_uuid, 'role': 'start_image'},
    {'value': after_uuid,  'role': 'end_image'}
  ],
  'duration': 4,
  'aspect_ratio': '1:1',
})
# Poll until done
mcp__claude_ai_higgsfield__job_status(jobId=...)
```

Embed as HTML5 video with poster image:

```html
<video controls preload="metadata" poster="{poster_url}" style="width:100%;max-width:680px;border-radius:10px">
  <source src="{video_url}" type="video/mp4">
</video>
```

### 7. Upload to WP media library

```python
# scripts/wp_media.py — pattern from inject_fat_diagram.py:
curl -u "$WP_USER:$WP_APP_PASSWORD" \
  -X POST \
  -H "Content-Disposition: attachment; filename=\"{slug}.png\"" \
  -H "Content-Type: image/png" \
  --data-binary @{file_path} \
  "${WP_SITE}/wp-json/wp/v2/media"
```

Then PUT with Hebrew alt/title/caption.

### 8. Inject into the post

Find the target text-editor widget, insert the figure HTML right after the section's closing tag (h2/ol/p). Use the validated marker pattern:

```python
DIAGRAM_HTML = f'<!-- {MARKER} -->\n<figure>...</figure>\n'
```

The MARKER lets you re-run safely (idempotent — replaces v1 with v2).

### 9. Push, clear cache, IndexNow

```python
update_elementor(post_id, new_data, clear_css=True)
clear_elementor_cache()
submit_indexnow(url)
```

### 10. Verify live

```python
# Cache-bust + check marker present in rendered HTML
fetch_live_html(url + '?cb=' + str(int(time.time())))
```

---

## Tools available in this skill

| Tool | Purpose |
|------|---------|
| `mcp__nano-banana__generate_image` | Path A — diagrams from prompt |
| `mcp__nano-banana__edit_image` | Path B — heavy transformation of source images |
| `mcp__nano-banana__continue_editing` | Iterative refinement |
| `mcp__claude_ai_higgsfield__models_explore` | Find right model for the job |
| `mcp__claude_ai_higgsfield__generate_image` | Higher-end image gen (Soul, Sora, Flux) |
| `mcp__claude_ai_higgsfield__generate_video` | Path C — image-to-video |
| `mcp__claude_ai_higgsfield__media_upload` | Upload reference images |
| `mcp__claude_ai_higgsfield__job_status` | Poll async jobs |
| `mcp__claude_ai_higgsfield__balance` | Check Higgsfield credits |
| Bash + Read | Apify scrape, WP REST, file management |

---

## Configuration

Required environment variables in `~/.dr-meir/credentials.env`:

```
WP_SITE=https://dr-meir.com
WP_USERNAME=<wp-user>
WP_APP_PASSWORD=<app-pass>
APIFY_API_TOKEN=<apify-token>
```

Higgsfield is connected via claude.ai Connectors (no API key needed in this skill — uses OAuth).

---

## Operating modes

User picks at the start of a run:

1. **Auto** — pick top candidate, transform, inject, done. Fastest.
2. **Semi-auto** ⭐ (recommended) — show top 3 transformed candidates, user picks one, inject. Default.
3. **Interactive** — show top 20 raw candidates, user marks relevant ones, transform 3, pick 1.

For Path C (video), always semi-auto minimum — preview before injection.

---

## Validated example (2026-05-04)

**Target:** Post 17924 (abdominal liposuction)
**Section:** "שומן תת-עורי" / "שומן ויסצרלי"
**Path chosen:** A (diagram)
**Result:** https://dr-meir.com/liposuction/abdominal-liposuction/

Steps:
1. Generated cross-section anatomy via nano-banana (no text labels — Gemini's Hebrew is broken)
2. Built v3 HTML overlay with 4 colored Hebrew labels (subcutaneous yellow, muscle red, visceral orange, organs blue)
3. Image at flex 1:1 380px-540px, labels at 240px-340px, ratio ~60:40
4. Uploaded to WP media (id 52526)
5. Injected after `</ol>` of the fat-types list
6. Cleared cache, IndexNow submitted, verified live

The "v3" iteration was the keeper after user feedback on v1 (image too small) and v2 (image on top, labels below). Final layout: image right, labels left (RTL = image on right, source order: image first), bigger image proportions.

---

## File map

```
~/.claude/skills/dr-meir-visuals/
├── SKILL.md                    # this file
├── README.md                   # GitHub readme
├── scripts/
│   ├── orchestrate.py          # main pipeline runner
│   ├── extract_keywords.py     # H1/H2/focus_keyword extraction
│   ├── translate_he_ru.py      # Hebrew → Russian (Claude does it inline)
│   ├── apify_instagram.py      # Apify scraper wrapper
│   ├── vision_filter.py        # Image scoring via Read tool
│   ├── path_a_diagram.py       # diagram generator
│   ├── path_b_transform.py     # image transformer
│   ├── path_c_video.py         # video generator (Higgsfield)
│   ├── wp_media.py             # upload to WP
│   └── inject_visual.py        # inject HTML into Elementor
├── templates/
│   ├── diagram_overlay.html    # the v3 figure pattern
│   ├── image_caption.html      # simple image caption
│   └── video_embed.html        # HTML5 video embed
└── examples/
    └── post-17924-fat-diagram.md   # validated run notes
```

Helper scripts re-use `~/.dr-meir/lib/wp_client.py` and `elementor_tree.py` (the existing infrastructure).

---

## Versioning

- v0.1 (2026-05-04): Initial — Path A validated end-to-end. Path B/C scaffolded; ready to run when caller invokes.
