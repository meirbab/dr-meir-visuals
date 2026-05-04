# Validated example: Subcutaneous vs Visceral Fat diagram (post 17924)

**Date:** 2026-05-04
**Target:** [https://dr-meir.com/liposuction/abdominal-liposuction/](https://dr-meir.com/liposuction/abdominal-liposuction/)
**Path:** A (diagram with Hebrew HTML overlay)
**Status:** ✅ Live

## What was done

The page had an existing list explaining the difference between subcutaneous fat (the kind that can be liposuctioned) and visceral fat (the kind that can't). It needed a visual to make the distinction obvious to a non-medical reader.

## Pipeline executed

1. **Located target section** — searched Elementor data for the literal `שומן תת-עורי` and `ויסצרלי`. Found two matching widgets; chose the first one (in the body, not in a related-content block).

2. **Generated image** with nano-banana:
   - Initial prompt asked for cross-section + Hebrew labels
   - Result: anatomy correct, but Hebrew text was garbled (`משויה הומיה אסכ-דד הומים עיון בצרוים` — Gemini cannot render Hebrew correctly)
   - Regenerated with English labels — better, but still had typos (`Subcuataneus`, `Viseral`)
   - Used `edit_image` to strip ALL text — final clean anatomy

3. **Uploaded to WP** media library:
   - Media ID: 52526
   - URL: `https://dr-meir.com/wp-content/uploads/2026/05/subcutaneous-vs-visceral-fat-diagram.png`
   - Hebrew alt + title + caption set via REST PUT

4. **Built HTML overlay** with 4 colored labels:
   - ① Subcutaneous fat — yellow card, ✓ green badge
   - ② Abdominal muscle — red card
   - ③ Visceral fat — orange card, ✗ red badge
   - ④ Internal organs — blue card

5. **Iterations on layout:**
   - **v1:** image left (380px max), labels right — image too small, lots of empty space
   - **v2:** image on top (700px), labels in 2x2 grid below — user preferred side-by-side
   - **v3** (final): image right (300-540px), labels left (240-340px), `align-items:center`, ratio ~60:40 — user approved

6. **Injected** right after the `</ol>` of the original fat-types list. Marker: `fat_diagram_v3_subcutaneous_visceral`. Cleared cache + IndexNow.

7. **Verified** live: 200 OK, marker present, image renders, all 4 labels visible, mobile-safe.

## Files produced

```
~/.dr-meir/campaigns/liposuction-rank1/
└── inject_fat_diagram.py             # the working script
```

The script supports automatic v1/v2 cleanup so re-running with a new MARKER replaces the old block atomically.

## Key learnings

1. **Gemini cannot render Hebrew in generated images** — always generate without text, add Hebrew via HTML overlay.
2. **Image proportion matters** — image dominant (~60% of figure width) feels balanced; smaller leaves empty space.
3. **Image right + labels left** (RTL = source-order: image first) feels natural for Hebrew readers.
4. **Color-coded labels** with accent border (5px, right side) make scanning fast.
5. **Always include a marker** in HTML comment for idempotent re-runs.
6. **Insert right after `</ol>`** of the section, not arbitrary location — keeps reading flow intact.

## Reproducibility

The same pattern would work for:
- Other anatomical concept pairs (e.g., dermis vs hypodermis for skin tightening pages)
- Treatment comparison diagrams (BodyTite vs VASER)
- Cause-effect diagrams (hormones → fat distribution)
- Step-by-step procedure illustrations

Just swap the diagram prompt and label set; the layout template stays identical.
