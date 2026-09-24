# Fingers (P8-3) — data audit + design skeleton

The P8-3 DATA AUDIT (measured 2026-09-24, S26 early-finish work — "what the
detection layer actually exposes of the 133 kps today") plus the design
skeleton S28 will build against. DESIGN SKELETON ONLY: nothing here is a
claim until a test, probe line, or gate number cites it; the build lands in
S28 per the session map, with the D-021 DECISIONS entry WRITTEN when that
code lands (never cited as existing before then — the round-3 strike S2
rule).

## The audit — where the 133 keypoints live today (measured)

COCO-WholeBody partition (pinned by an assertion in
`core/src/riggermortis/inference/poses.py`): 17 body + 6 foot + 68 face +
21 + 21 hand = 133. Index ranges are NAMED CONSTANTS: `FACE_START 23 /
FACE_END 91`, `HAND_L_START 91 / HAND_L_END 112`, `HAND_R_START 112 /
HAND_R_END 133` — P8-3 consumes the hands through these constants, never
re-typed literals.

| stage | hands/face present? | measured on the P1-9 photo (real models) |
|---|---|---|
| ONNX output (`detect_keypoints`) | YES — the wrapper asserts the 133-simcc shape | all 133 emitted |
| `Figure` (`inference/poses.py`) | YES — all 133 kps + 133 confidences, validated `!= 133` raises | — |
| `rigpose detect --json` (detection payload) | YES — full 133 + confidences ride | hand.L conf mean **0.650** max 0.700, 0/21 zero; hand.R mean **0.857** max 0.894, 0/21 zero; face mean **0.958**, 0/68 zero; body mean 0.812 |
| `observations_from_keypoints` (solve input) | NO — maps ONLY the 17 body + 6 foot indices; hand/face indices never read | the drop point |
| `CanonicalPose` / pose payload (`pose` dict) | NO — 22 canonical roles only | `positions` keys = the 22 roles |

**Conclusion (measured, not assumed): the finger data already flows
end-to-end to the DETECTION payload with per-keypoint confidences — the
per-finger visibility gate signal P8-3 needs is already shipped. The drop
happens at the canonical-solve boundary** (`observations_from_keypoints`
reads only body/foot indices), so P8-3 is a SOLVE+PAYLOAD+APPLY extension,
not a detector change. No new model, no new download, no wrapper change
(P6-6's never-list untouched).

## Design skeleton (S28 fills this in; each section becomes as-built there)

1. **Payload path (ADDITIVE, format 3 unchanged)**: a new optional
   top-level `hands` field — per figure… carried per FIGURE entry (each
   entry gains optional `hands`: `{"hand.L": {"wrist": [x, y, conf], …21
   kps}, "hand.R": {…}}`) so a figure's hands travel with the figure.
   Readers that ignore unknown fields keep working byte-identically (the
   standing policy); the contract test pins a hands-free payload byte
   shape. COCO-WholeBody hand layout: kp 0 = wrist, then 5 fingers × 4
   (mcp/pip/dip/tip) in the fixed order thumb→index→middle→ring→pinky —
   pinned by named constants added to `poses.py` in the same commit.
2. **Solve (per hand, per finger)**: finger chains solve ONLY from observed
   kps — each of the 5 fingers gets a 3-joint direction chain (mcp→pip,
   pip→dip, dip→tip in canonical units, wrist-anchored, hand-frame from the
   canonical wrist→forearm direction). Per-finger confidence gate: a finger
   is SOLVED iff its chain's kp confidences clear the declared floor
   (D-008-order-of-magnitude default, declared untuned); below it the
   finger is SKIPPED + FLAGGED — a wrong finger reads as broken, an absent
   one reads as clean (the roadmap's honesty rule; Annex A.1 demands 100%
   gated-skip on the occlusion fixtures: hand-behind-back, clenched fist).
3. **Canonical namespace (the D-021 amendment)**: `hand.L.finger.<name>[0..2]`
   chains (`thumb`, `index`, `middle`, `ring`, `pinky`) in a SEPARATE
   additive map — the frozen 22-role core untouched; consumers that ignore
   fingers work unchanged. The DECISIONS entry D-021 is WRITTEN at this
   landing (additive-map format version + policy coverage per the roadmap's
   standing constraints). Nothing renames, nothing reorders.
4. **Apply**: finger bones via the preset mapping (authored once per rig in
   the preset's additive `hands` binding — the P6-1a `secondary` pattern);
   `bake_action`/`apply_payload` gain the additive binding, validated
   against the live rig (exists, parent-first under the mapped hand bone).
   A rig without finger targets reports a LOUD capability line, never a
   silent no-op (the P8-4 two-class pattern's precedent).
5. **Accept bars (Annex A.1, pre-declared)**: 20-pose hand benchmark
   (fist/spread/grip/pinch…): per-finger direction error median ≤ 20°,
   p90 ≤ 35° on VISIBLE fingers; occlusion fixtures (hand-behind-back,
   clenched) 100% gated-skip; metarig + Mixamo-class apply ≤ the FK family
   bar. The measured audit above (hand conf means 0.65–0.86 on a real
   photo, zero dropouts) says the confidence signal is strong enough to
   gate on — the benchmark measures the DIRECTION bars.
6. **Policy (D-019)**: fingers carry no content by themselves — no new
   policy surface; the add-on's existing subject checks apply unchanged.

## What P8-3 deliberately does NOT do (until its own session says so)

- No face work (P8-4's 68-kp table is its own design page section).
- No payload format 4 (v3 stays; `hands` is an ADDITIVE field).
- No re-solve of the body from hand kps (the wrist stays the boundary).
- No live-mode finger streaming (rides P5's existing pipeline after the
  static path is proven).
