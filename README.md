# dr-meir-visuals

AI visual enrichment pipeline for [dr-meir.com](https://dr-meir.com), a Hebrew-language WordPress site for Dr. Meir Babaev's dermatology + aesthetic-medicine clinic.

A Claude Code Skill that takes any post on the site and adds AI-generated visuals — anatomical diagrams, transformed concept images, or before/after videos — at the right semantic location, with Hebrew-aware HTML overlay labels and full mobile responsiveness.

---

## Capabilities

| Path | Output | Source | Tools |
|------|--------|--------|-------|
| **A** | Anatomical / explainer diagram | text-prompt | nano-banana `generate_image` |
| **B** | Transformed concept image | Apify Instagram → AI edit | Apify + nano-banana `edit_image` |
| **C** | Before/after motion video | user-supplied real images | Higgsfield `generate_video` |

The skill is invoked by Claude Code automatically when you ask "enrich post X with a visual", "add diagram for the abdominal page", "create before/after video for thigh post", etc.

---

## Quick start

In a Claude Code session with the skill installed:

```
> Add a diagram of the difference between subcutaneous and visceral fat
> to the abdominal-liposuction page (post 17924).
```

The skill will:
1. Fetch the post via WP REST and find the right injection point
2. Generate the image via nano-banana (without Hebrew text — Gemini can't render it)
3. Build the figure HTML using the validated v3 layout (image right, labels left)
4. Upload to WP media library with Hebrew alt/title/caption
5. Inject into the Elementor data after the matching section
6. Clear cache + ping IndexNow
7. Verify the change is live

---

## Why a separate skill?

This site has unique characteristics that warrant its own skill:

- **RTL Hebrew** content with English/Russian image generation prompts
- **Elementor + Rank Math + WP Rocket** stack with mobile gotchas (extra root containers break the footer)
- **Medical-grade ethics** — before/after photos must be from real patients with consent
- **Validated visual layout** — the v3 figure pattern with image-right + colored RTL labels was iterated on with the user 3 times; baking it into a template means we don't reinvent the wheel each time

---

## Configuration

Required in `~/.dr-meir/credentials.env`:

```
WP_SITE=https://dr-meir.com
WP_USERNAME=...
WP_APP_PASSWORD=...
APIFY_API_TOKEN=apify_api_...
```

**Higgsfield** is connected via claude.ai Connectors (OAuth, no token in env).
**nano-banana** uses `GEMINI_API_KEY` from environment.

---

## Files

```
.
├── SKILL.md                     # Skill spec — Claude Code reads this
├── README.md                    # this file
├── scripts/
│   ├── orchestrate.py           # main pipeline runner
│   ├── extract_keywords.py      # H1/H2/H3/focus_keyword extraction from WP
│   ├── apify_instagram.py       # Apify hashtag scraper wrapper
│   ├── wp_media.py              # upload to WP with Hebrew meta
│   └── inject_visual.py         # insert HTML block into Elementor at right spot
├── templates/
│   ├── diagram_overlay.html     # validated v3 figure pattern (image+labels)
│   └── video_embed.html         # HTML5 video embed
└── examples/
    └── post-17924-fat-diagram.md  # successful run notes
```

---

## Validated example

Post 17924 (abdominal liposuction) got a subcutaneous-vs-visceral fat diagram on 2026-05-04. See [`examples/post-17924-fat-diagram.md`](examples/post-17924-fat-diagram.md) for the full step-by-step.

Live page: https://dr-meir.com/liposuction/abdominal-liposuction/

---

## Ethics

**Path C (image-to-video) only with real, consented patient photos** owned by Dr. Meir's clinic. Israeli medical-board ethics rule: presenting another clinic's results as your own is a code violation regardless of how the image was sourced or transformed.

**Path A and B** are fine with AI-generated or AI-transformed inspiration sources because they show concept/illustration, not specific clinical results.

---

## Versioning

- **v0.1** (2026-05-04): Initial — Path A validated end-to-end. Path B/C scaffolded; ready to run when invoked.

---

## License

MIT — see [LICENSE](LICENSE).
