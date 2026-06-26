# Plana Maid Cat-Ears Full Regeneration Report

## Scope

`plana-cat-maid` is a separate pet variant. It does not replace `plana`.

This pass regenerated the full Plana maid cat-ear module set from generated source grids:

- 9 atlas rows
- 30 extra states
- 39 total generated source grids
- 360 extra PNG frames

The final visible modules are generated-source derived. Local scripts were only used for chroma removal, frame slicing, sizing, atlas packing, QA images, and validation.

## Hard Rules

- No local drawing, painting, mirroring, flipping, patching, or assembling was used to create visible module elements.
- Screen-edge black boundaries, laptops, placards, check marks, X marks, magnifiers, hands, halo, hair ornaments, and costume details must be present in the generated source image for that state.
- Left-edge states place the black boundary on the left and the character on the right.
- Right-edge states place the black boundary on the right and the character on the left.

## Outputs

- `shared/Characters/plana-cat-maid/spritesheet.png`
- `shared/Characters/plana-cat-maid/spritesheet.webp`
- `shared/Characters/plana-cat-maid/openplana-character.json`
- `shared/Characters/plana-cat-maid/pet.json`
- `shared/Characters/plana-cat-maid/extra/*/*.png`
- `shared/Characters/plana-cat-maid/qa/*.png`

## Verification

```bash
python3 mac_os/script/process_neo_action_assets.py --manifest .codex/tmp/neo-pets/action-generation-manifest-plana-cat-maid-fullregen.json --character plana-cat-maid
python3 mac_os/script/validate_pet_assets.py --character plana-cat-maid
python3 mac_os/script/audit_frame_overlays.py --character plana-cat-maid --json-out .codex/tmp/neo-pets/plana-cat-maid-fullregen-overlay-audit.json
python3 mac_os/script/validate_neo_artifacts.py --character plana-cat-maid --include-atlas --candidate-sheet-dir .codex/tmp/neo-pets/plana-cat-maid-fullregen-qa --json-out .codex/tmp/neo-pets/plana-cat-maid-fullregen-neo-artifact-check.json --summary
```

Results:

```text
processed_count=39
pet assets ok
overlay audit ok=true, sizeIssues=0, positionWarnings=0, mirrorWarnings=0
neo artifact check ok=true, motionIssues=0, cutoutIssues=0, sizeCandidates=0
```

QA evidence:

- `shared/Characters/plana-cat-maid/qa/atlas-contact-sheet.png`
- `shared/Characters/plana-cat-maid/qa/all-extra-expression-overview.png`
- `shared/Characters/plana-cat-maid/qa/edge-all-contact-overview.png`
- `shared/Characters/plana-cat-maid/qa/atlas-idle-contact-sheet.png`
- `shared/Characters/plana-cat-maid/qa/edge-peek-right-contact-sheet.png`
- `shared/Characters/plana-cat-maid/qa/edge-success-right-contact-sheet.png`
