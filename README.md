# dr-meir-visuals

Visual + content enrichment pipeline for [dr-meir.com](https://dr-meir.com), a Hebrew-language WordPress site for Dr. Meir Babaev's dermatology + aesthetic-medicine clinic.

A Claude Code Skill that takes a target post URL plus a handful of Instagram links — links you already curated by hand — and turns them into clean, brand-stripped images, a transformation morph video, and an enrichment text block + new FAQs mined from the post captions.

---

## What v0.3 changed

The previous version (v0.2) ran a hashtag-based Apify scrape and asked Claude to vision-rank candidates. This was slow, unreliable, and hit unrelated content.

**v0.3** flips the model: **you** find the right Instagram posts manually (you'll always do better at this than vision filtering will). The skill takes those URLs as input, then runs the full automation: cleaning → video → caption mining → page injection.

Default behavior when you don't say anything: every image gets text/logos/watermarks removed, the original background swapped for a clean neutral studio gradient, and a mild enhancement applied. Then a 5-second Kling 3.0 morph video is generated from the first image. Then captions are mined for clinical facts, statistics, and mechanisms not yet on the page, and injected as a new science block + new FAQ tabs.

---

## Quick start

```bash
# Single command run — Claude picks up the plan and executes the MCP calls.
python3 scripts/orchestrate.py 52464 \
    --ig https://www.instagram.com/p/B_Foa3ZlcQ3/ \
         https://www.instagram.com/p/CAzblOKFzNT/ \
         https://www.instagram.com/p/BhZO5pNnb8e/
```

Or in plain English to Claude:

> Enrich `https://dr-meir.com/liposuction/knee-liposuction/` with these IG links:
> https://www.instagram.com/p/B_Foa3ZlcQ3/, https://www.instagram.com/p/CAzblOKFzNT/, https://www.instagram.com/p/BhZO5pNnb8e/

The skill will:
1. Fetch each IG post via Apify URL mode (image + full caption)
2. NSFW pre-crop + upload to Higgsfield + run nano_banana_2 to remove text/logos and replace the background
3. Generate one Kling 3.0 morph video from the first image (split into BEFORE/AFTER halves)
4. Upload all media to WP and replace the page's existing galleries (the last gallery becomes the video widget)
5. Mine the captions and inject a science block + 2-5 new FAQs in Hebrew, with heading fixes for any leftover wrong-page keywords
6. Cache flush + IndexNow + verify live

---

## Brief overrides

Append a free-text brief to override defaults:

| You say... | Skill does |
|---|---|
| "skip video" / "בלי וידאו" | step 5 skipped |
| "skip text" / "בלי טקסט" | caption mining skipped |
| "don't change background" | bg-replacement bullet dropped from cleaning prompt |
| "make 2 videos" | Kling step runs twice on different image pairs |
| "place text after `<heading>`" | overrides default insertion point (default: before FAQ) |
| "use only image 2" | filters image set down to that one |
| "video should be 8s" | passes through to Kling duration |

Anything not matching a recognized intent is appended to the cleaning prompt as additional clinical context.

---

## Configuration

`~/.dr-meir/credentials.env`:

```
WP_SITE=https://dr-meir.com
WP_USERNAME=...
WP_APP_PASSWORD=...
APIFY_API_TOKEN=apify_api_...
```

Higgsfield is connected via claude.ai Connectors (OAuth, no API key in env).
nano-banana (fallback path) reads `GEMINI_API_KEY` from environment.

---

## Files

```
.
├── SKILL.md                                # full skill spec for Claude (v0.3)
├── README.md                               # this file
├── LICENSE                                 # MIT
├── scripts/
│   ├── orchestrate.py                      # v0.3 IG-links pipeline planner
│   ├── apify_instagram.py                  # rewritten — directUrls mode
│   ├── extract_keywords.py                 # used during caption mining
│   ├── clean_image_higgsfield.py           # image cleaning + halve-for-morph helper
│   ├── generate_morph_video.py             # split + Kling 3.0 morph + embed HTML
│   ├── mine_captions.py                    # caption → enrichment plan
│   ├── replace_galleries_with_media.py     # gallery + video widget swap
│   ├── wp_media.py                         # upload media to WP
│   └── inject_visual.py                    # insert HTML block into Elementor
├── templates/
│   ├── diagram_overlay.html                # legacy v0.1 diagram template
│   ├── video_embed.html                    # video figure (manual mode)
│   ├── clean_default.txt                   # default nano_banana_2 cleaning prompt
│   └── morph_default.txt                   # default Kling 3.0 morph prompt
└── examples/
    ├── post-17924-fat-diagram.md           # v0.1 run notes (anatomical diagram)
    └── post-52464-knee-ig-pipeline.md      # v0.3 run notes (IG-link enrichment)
```

---

## Validated example (v0.3)

Post 52464 (knee liposuction) on 2026-05-05. Three real IG before/after photos →
3 cleaned images + 1 Kling 3.0 morph video + α/β-receptor science block +
4 new FAQ tabs + 2 heading fixes. See [`examples/post-52464-knee-ig-pipeline.md`](examples/post-52464-knee-ig-pipeline.md).

Live page: https://dr-meir.com/liposuction/knee-liposuction/

---

## Ethics

The cleaned images are heavily AI-transformed (text removed, background replaced, mild enhancement). They are still derived from real before/after photos posted publicly on Instagram by working clinicians. You are responsible for ensuring you have the right to use the patient likeness — the skill assumes you've vetted that.

For purely synthetic before/after images (no patient sourced), use a different skill or generate from prompt only.

---

## Versioning

- **v0.3** (2026-05-05): IG-link input model. No more keyword scraping. Default automatic cleaning + morph video + caption mining. Validated end-to-end on post 52464.
- **v0.2** (2026-05-04, evening): Hashtag scraper + nano-banana edit pipeline. Validated on post 52464 (image-only).
- **v0.1** (2026-05-04, morning): Initial — diagram-from-prompt path. Validated on post 17924.

---

## License

MIT — see [LICENSE](LICENSE).
