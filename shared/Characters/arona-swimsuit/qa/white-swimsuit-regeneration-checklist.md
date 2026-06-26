# Arona White Swimsuit Regeneration Checklist

## Current State

The `shared/Characters/arona` directory is the renamed former `arona-neo` resource set. Its current atlas and extra frames still show the older blue-white uniform identity. A full white-swimsuit replacement still requires new generated `source-grid-chroma.png` images before the existing processing scripts can create final transparent frames.

Reference image:

`shared/Characters/arona/references/white-swimsuit-reference.png`

Target identity:

Arona as a compact Q-version desktop pet, based on the reference: pale blue-white bob hair, visible bright blue eye, cyan-blue floating halo with a real open center, white swimsuit, white paw gloves, white paw boots, soft blue tail, small pink hair accents, gentle energetic expression, clean anime sprite linework, readable at 256x256.

Do not flip identity details. Keep the halo tilt, hair part, side braid or side hair accents, face orientation, tail attachment, and accessory placement consistent with the reference unless the state explicitly needs a new pose.

## Generation Requirements

Use magenta chroma key `#FF00FF` for every source grid. Empty pixels, gutters, and unused slots must be exact flat magenta with no shadows, glow, gradients, checkerboard, scenery, text, labels, frame numbers, borders, or guide marks.

Generate source grids, then process them through repo scripts. Do not hand-edit, mirror, rotate, crop, or paint existing source images outside the scripts.

Generate these atlas rows:

- `idle`
- `running-right`
- `running-left`
- `waving`
- `jumping`
- `failed`
- `waiting`
- `running`
- `review`

Generate these extra states:

- `idle-normal`
- `awaiting`
- `idle-read`
- `idle-sleep`
- `coding`
- `checking`
- `rejected`
- `success`
- `pinched`
- `carried`
- all `edge-*` states currently listed in `openplana-character.json`

Edge states must be generated per side. Do not make `edge-*-right` by mirroring `edge-*-left`, and do not make `edge-*-left` by mirroring `edge-*-right`.

Left edge states:

The screen boundary is on the left. Arona must appear on the right side of that boundary, leaning inward from behind it, with most of the body hidden off-screen.

Right edge states:

The screen boundary is on the right. Arona must appear on the left side of that boundary, leaning inward from behind it, with most of the body hidden off-screen.

Idle rows:

Keep frame-to-frame changes small and stable. No sudden blink, closed-eye frame, open-mouth jump, width jump, center jump, halo jump, tail pop, or accessory pop. The first and last frames must match cleanly.

## Base Prompt

```text
Use case: stylized-concept
Asset type: OpenPlana Arona desktop pet source art
Primary request: Create Arona as a compact 3-head Q-version anime desktop pet based on the attached white swimsuit reference image.
Subject: pale blue-white bob hair, visible bright blue eye, cyan-blue floating halo with an open center, white swimsuit, white paw gloves, white paw boots, soft blue tail, small pink hair accents, gentle energetic expression.
Style: clean anime sprite linework, soft crisp shading, readable at 256x256.
Background: perfectly flat solid #FF00FF chroma key, no shadows, no gradients, no texture.
Constraints: full body visible with generous padding, no text, no watermark, no scenery, no floor shadow, no glow, no motion effects.
Avoid: flipped identity details, filled halo center, cropped halo, cropped tail, cropped paws, extra props, old blue-white uniform.
```

## Row Prompt Template

```text
Create an exact 12-frame chroma-key sprite source grid for Arona, state <STATE>, arranged as a 4 columns x 3 rows grid. Use the white swimsuit reference image and the approved Arona base identity. Each slot contains one complete pose on flat #FF00FF. Read frames left to right, top to bottom. Adjacent frames transition naturally. The first and last frames match cleanly when loop=true. Keep Arona identity stable: halo, hair direction, side accents, face, tail, swimsuit, paw gloves, and paw boots stay consistent. Do not draw guide lines, frame numbers, text, shadows, glow, speed lines, dust, wave marks, or detached effects. Do not let pixels cross into adjacent slots.
Action: <ACTION>
Side rule: <SIDE_RULE>
Loop: <true|false>
```

## Processing Commands

These commands assume generated grids are staged under `.codex/tmp/neo-pets/generated/arona/...`.

```bash
python3 mac_os/script/process_neo_action_assets.py --character arona --state <state>
```

## Verification Commands

```bash
python3 mac_os/script/validate_neo_artifacts.py --character arona --include-atlas --strict-visual-candidates --candidate-sheet-dir shared/Characters/arona/qa/visual-candidates --json-out shared/Characters/arona/qa/neo-artifact-check.json --summary
```

```bash
python3 mac_os/script/audit_frame_overlays.py --character arona --json-out "$PWD/shared/Characters/arona/qa/overlay-audit.json"
```

Manual visual checks:

- `shared/Characters/arona/qa/atlas-contact-sheet.png`
- `shared/Characters/arona/qa/edge-all-contact-overview.png`
- `shared/Characters/arona/qa/idle-normal-contact-sheet.png`
- `mac_os/docs/qa/current-target/overlay-audit/arona/overview.png` when generated

Pass conditions:

- `validate_neo_artifacts.py` prints `ok=true`.
- `audit_frame_overlays.py` prints `ok=true`.
- Idle has no frame jump, blink spike, center jump, halo jump, tail pop, or mouth pop.
- Left and right edge states are side-authored poses, not mirrored pairs.
- Right edge states keep Arona on the left side of the right boundary.
- Halo, hair, tail, paw gloves, paw boots, and side accents preserve the white-swimsuit reference identity.
