# Plana Maid Cat-Ears Regeneration Report

## Current State

`shared/Characters/plana` is the active Plana resource directory. The old neo-named Plana directory is no longer present.

The current source, atlas, extra frames, and edge frames use the maid outfit and cat-ear identity from the requested reference:

- black-and-white maid dress
- white apron and frills
- black bow and white cuffs
- white cat ears with pink inner fur
- red oval halo
- long white hair with the pale pink braid on the viewer's right

The generated source image is copied to:

`shared/Characters/plana/qa/source-green.png`

The selected generated source path was:

`/Users/tanshow/.codex/generated_images/019effbc-11bb-7d20-8936-13c6985d5251/ig_04a3a6c5d77737f9016a3d600ad13c81999150948f1609aeb1.png`

## Generation Prompt

```text
Use case: stylized-concept
Asset type: OpenPlana desktop pet identity source image
Primary request: Create one full-body chibi Q-version Plana desktop pet identity image, grounded in the attached reference image. Plana wears the exact black-and-white maid outfit from the reference: black dress, white apron with ruffled trim, black bow, white frilled headpiece/headband, white wrist cuffs, and black skirt. Add small cat ears on top of the head, with white outer fur and soft pink inner fur. Preserve Plana identity and orientation: long white hair with pale pink side/braid strand on the viewer's right, reserved gray-lavender visible eye, small closed mouth, thin red/pink oval halo above the head tilted the same way as the reference, black headband/maid headpiece direction not flipped. Compact 3-head anime chibi proportions, clean sprite linework, soft crisp shading, readable at 256x256.
Scene/backdrop: perfectly flat solid #00ff00 chroma-key background only.
Composition/framing: one centered complete full-body character, standing calmly, hands relaxed near chest or sides, generous padding around hair, halo, ears, hands, skirt, and feet.
Constraints: no weapon, no umbrella, no long horizontal prop, no readable text, no watermark, no scenery, no floor, no cast shadow, no glow, no detached effects. Do not use #00ff00 anywhere in the character, outfit, halo, ears, highlights, or shadows. Keep edges clean and separated from the background.
Avoid: white background, transparent checkerboard, gradients, texture, shadows, duplicated character, cropped halo, cropped hair, cropped ears, cropped feet, flipped identity, changed hair orientation, filled halo center, extra props.
```

## Processing

The base source was processed with the repository script:

```bash
python3.10 mac_os/script/build_neo_pet_base_assets.py --id plana --display-name '普拉娜' --description '穿女仆装与猫耳的普拉娜 Q 版桌宠。' --source /Users/tanshow/.codex/generated_images/019effbc-11bb-7d20-8936-13c6985d5251/ig_04a3a6c5d77737f9016a3d600ad13c81999150948f1609aeb1.png --force
```

Plana-only deterministic assembly then regenerated:

- `spritesheet.png`
- `spritesheet.webp`
- 30 `extraStates`
- 360 extra PNG frames
- per-state contact sheets
- edge overview
- idle overlay
- boundary and idle JSON checks

Left and right edge states preserve the same Plana orientation. Right edge states place Plana to the left of the right boundary; left edge states place Plana to the right of the left boundary.

## Verification

```bash
python3 mac_os/script/validate_neo_artifacts.py --character plana --include-atlas --summary --json-out shared/Characters/plana/qa/neo-artifact-check.json --candidate-sheet-dir shared/Characters/plana/qa/candidate-sheets
```

Result:

```text
ok=true
motionIssues=0
cutoutIssues=0
sizeCandidates=0
blinkCandidates=0
closedEyeCandidates=0
openMouthCandidates=0
backFacingCandidates=0
carryFacingCandidates=0
adjacentFrameCandidates=0
propCandidates=216
```

`propCandidates` is non-fatal here. The validator flags dark/light horizontal runs from the maid outfit, laptop, placards, and similar state materials; it still returned `ok=true`.

Custom Plana boundary and idle check:

```text
ok=True
idle_max_center_delta=1.00
atlas_idle_max_center_delta=1.00
edge_states=20
min_mirror_diff=0.0347
```

Evidence files:

- `shared/Characters/plana/qa/atlas-contact-sheet.png`
- `shared/Characters/plana/qa/all-extra-expression-overview.png`
- `shared/Characters/plana/qa/edge-all-contact-overview.png`
- `shared/Characters/plana/qa/idle-normal-overlay.png`
- `shared/Characters/plana/qa/plana-boundary-idle-check.json`
- `shared/Characters/plana/qa/edge-orientation-check.json`
