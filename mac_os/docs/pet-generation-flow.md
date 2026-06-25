# OpenPlana Pet Generation Flow

## Previous Flow

1. Write an action manifest from `openplana-character.json`.
2. Generate chroma-key source sheets for the atlas rows and every extra state.
3. Run `process_neo_action_assets.py` to remove chroma background, normalize each frame to `256x256`, build the atlas, and update state frame paths.
4. Generate contact sheets and run asset validators.

The weak point was edge-state recovery: some edge modules were derived from normal states or repaired by geometry. That made it too easy to introduce large offsets, wrong dock-side lines, simple left/right mirrors, or flipped identity cues such as hair ornaments and halo direction.

## Improved Flow

1. Treat `plana` and `arona` as final runtime ids. Legacy `*-neo` ids are only migration inputs.
2. Generate each edge module as its own source art. Do not create the right side by mirroring the left side, and do not use normal-state crops as final edge art.
3. For Plana, use the maid reference and add white cat ears with pink inner fur. For Arona, use the white-swimsuit reference. Preserve each character's original orientation cues.
4. Use local scripts only for pipeline processing: chroma removal, slicing, sizing, atlas packing, manifest updates, and QA images. Do not patch character pixels, flip source art, erase accessories, or hand-edit image content.
5. Reject source sheets when the dock-side line, halo opening, frame spacing, face width, or idle motion stability is wrong. Regenerate the source sheet instead.
6. Run all checks before sync:
   - `mac_os/script/validate_pet_assets.py`
   - `mac_os/script/validate_neo_artifacts.py --character plana --character arona --summary --strict-visual-candidates --include-atlas`
   - `mac_os/script/audit_frame_overlays.py --character plana --character arona`
   - `mac_os/script/build_and_run.sh --verify`

## Edge Checks Added

- Dock-side black edge line must exist on the correct canvas side.
- The opposite side must not contain a second black edge line.
- Visible character content must sit close to the correct edge line.
- Overlay audit reports idle jumps and left/right edge pairs that look like simple mirrored silhouettes.
