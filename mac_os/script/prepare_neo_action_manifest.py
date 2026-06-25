#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
DEFAULT_SCHEMA = CHARACTER_ROOT / "plana-neo" / "openplana-character.json"
DEFAULT_OUTPUT = REPO_ROOT / ".codex" / "tmp" / "neo-pets" / "action-generation-manifest.json"

ATLAS_ROWS = [
    ("idle", "quiet idle loop with subtle breathing, visible eye kept open and steady, hands close to body, no original weapon or umbrella prop"),
    ("running-right", "rightward drag movement through body and limb posture only, no speed lines"),
    ("running-left", "leftward drag movement through body and limb posture only, no speed lines"),
    ("waving", "small hand wave shown through arm pose only, no wave marks"),
    ("jumping", "vertical jump through body position only, no shadow or landing marks"),
    ("failed", "holding a rectangular failure placard board with a bold red X mark on the board, no readable text"),
    ("waiting", "patient expectant waiting pose, quiet and attentive"),
    ("running", "focused task-work pose, processing or typing energy, no literal sprinting"),
    ("review", "focused checking pose through lean, eyes, and head tilt"),
]

EXTRA_ACTIONS = {
    "carried": "front-facing carried pose: the character faces the screen while a simple pale hand enters from the top edge and pinches the back collar or nape-side collar; body suspended vertically below the grip, head slightly lowered but face still visible, arms hanging straight down, legs hanging limp, no back view, no rear-facing pose, no side-only pose, no sitting, no kneeling, no curled pose, no standing on a floor",
    "edge-peek-left": "leaning diagonally inward while peeking out from behind the left screen edge toward the right; most of the body remains hidden off-screen, with only one side of the face, one shoulder, hair, and one hand protruding",
    "edge-peek-right": "leaning diagonally inward while peeking out from behind the right screen edge toward the left; most of the body remains hidden off-screen, with only one side of the face, one shoulder, hair, and one hand protruding",
    "idle-read": "calm reading loop, small head and book movement, no readable page text",
    "idle-normal": "quiet standing loop with the original gun or umbrella prop held low, subtle breathing, hands close to body",
    "idle-sleep": "sleeping loop, closed eyes, subtle head bob, halo stable",
    "coding": "kneeling or sitting with a compact laptop computer, small hand movement, no readable UI text",
    "checking": "focused inspection pose with magnifier, subtle lean, visible eye kept open and steady, no symbols",
    "awaiting": "expectant waiting pose, quiet and patient, no waving",
    "rejected": "holding a rectangular failure placard board with a bold red X mark on the board, no readable text",
    "success": "holding a rectangular success placard board with a bold green check mark on the board, no readable text",
    "edge-success-left": "left edge completion peek pose, leaning diagonally inward from behind the left edge while holding a success placard board with a bold green check mark, no readable text",
    "edge-success-right": "right edge completion peek pose, leaning diagonally inward from behind the right edge while holding a success placard board with a bold green check mark, no readable text",
    "pinched": "cheek-pinched reaction redrawn as one integrated pose, visible eye kept open and steady, no wink, no squeezed-shut eyes, no overlay layer look",
    "edge-idle-read-left": "left edge reading peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, book peeks out with the upper body, no readable text",
    "edge-idle-read-right": "right edge reading peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, book peeks out with the upper body, no readable text",
    "edge-idle-normal-left": "left edge quiet idle peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, stable exposed face and shoulder width",
    "edge-idle-normal-right": "right edge quiet idle peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, stable exposed face and shoulder width",
    "edge-idle-sleep-left": "left edge sleepy peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, closed eyes, halo stable",
    "edge-idle-sleep-right": "right edge sleepy peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, closed eyes, halo stable",
    "edge-coding-left": "left edge coding peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, compact laptop peeks out with the hands, no readable UI text",
    "edge-coding-right": "right edge coding peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, compact laptop peeks out with the hands, no readable UI text",
    "edge-checking-left": "left edge focused inspection peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, no symbols",
    "edge-checking-right": "right edge focused inspection peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, no symbols",
    "edge-awaiting-left": "left edge expectant peek loop; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, quiet and patient",
    "edge-awaiting-right": "right edge expectant peek loop; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, quiet and patient",
    "edge-rejected-left": "left edge rejected peek pose; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, holding a failure placard board with a bold red X mark, no readable text",
    "edge-rejected-right": "right edge rejected peek pose; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, holding a failure placard board with a bold red X mark, no readable text",
    "edge-pinched-left": "left edge cheek-pinched peek reaction; the character leans diagonally inward from behind the left screen edge, most of the body remains hidden, integrated pose",
    "edge-pinched-right": "right edge cheek-pinched peek reaction; the character leans diagonally inward from behind the right screen edge, most of the body remains hidden, integrated pose",
}

CHARACTERS = {
    "plana-neo": {
        "display": "普拉娜-neo",
        "reference": "/Users/tanshow/.codex/attachments/a8d82b9e-9ad7-4df2-8e55-ea4281fb39f7/image-1.png",
        "identity": (
            "Use only the user-provided Plana standing illustration and the generated plana-neo base from this run. "
            "Do not use any existing Plana desktop-pet image, old sprite, old generated image, or old prompt as identity reference. "
            "Preserve white hair, black headband, tall white ribbon-like hair ornament, long white hair with faint pale pink strand, "
            "reserved gray-lavender visible eye, black sailor uniform, white neckerchief, dark pleated skirt, long black coat, black boots, "
            "and slim dark horizontal weapon or umbrella."
        ),
        "no_prop_identity": (
            "Use only the user-provided Plana standing illustration and the generated plana-neo base from this run. "
            "Do not use any existing Plana desktop-pet image, old sprite, old generated image, or old prompt as identity reference. "
            "Preserve white hair, black headband, tall white ribbon-like hair ornament, long white hair with faint pale pink strand, "
            "reserved gray-lavender visible eye, black sailor uniform, white neckerchief, dark pleated skirt, long black coat, and black boots. "
            "Do not draw the slim dark horizontal weapon, umbrella, gun, staff, rifle, sheath, or any long horizontal prop."
        ),
        "key_color": "#00FF00",
        "key_label": "green",
        "halo": (
            "Small thin red oval halo, matching the provided standing illustration. Red line only; no white highlight, no inner white ring, "
            "no glow, no filled center. The halo opening must show the exact chroma-key color."
        ),
    },
    "arona-neo": {
        "display": "阿罗娜-neo",
        "reference": "/Users/tanshow/.codex/attachments/a8d82b9e-9ad7-4df2-8e55-ea4281fb39f7/image-2.png",
        "identity": (
            "Use the user-provided Arona standing illustration and the generated arona-neo base from this run. Preserve short pale blue-white bob hair, "
            "right side braid, large white bow-like head ornament, one visible bright blue eye, gentle smile, blue translucent sailor top, white collar, "
            "large white chest bow, white pleated skirt, white shoes, and white-blue umbrella with small blue charm."
        ),
        "no_prop_identity": (
            "Use the user-provided Arona standing illustration and the generated arona-neo base from this run. Preserve short pale blue-white bob hair, "
            "right side braid, large white bow-like head ornament, one visible bright blue eye, gentle smile, blue translucent sailor top, white collar, "
            "large white chest bow, white pleated skirt, and white shoes. Do not draw the umbrella, charm, gun, staff, rifle, sheath, or any long horizontal prop."
        ),
        "key_color": "#FF00FF",
        "key_label": "magenta",
        "halo": (
            "Small cyan-blue floating ring matching the provided standing illustration. The center must be a real open hole showing the exact chroma-key color; "
            "no white or blue filled disk, no glow filling the center."
        ),
    },
}


def is_edge_state(state: str, side: str | None = None) -> bool:
    if not state.startswith("edge-"):
        return False
    if side is None:
        return state.endswith("-left") or state.endswith("-right")
    return state.endswith(f"-{side}")


def side_rule(state: str) -> str:
    if is_edge_state(state, "left"):
        return (
            "Left edge state source art: do not draw any black screen-edge line, guide line, border, or vertical separator in the source sheet. "
            "Pose the character as if peeking inward from behind an invisible left screen edge: the character must appear on the right side of that left boundary. "
            "Most of the body remains hidden behind/off-screen at the left boundary, with only 35-55 percent of the body width visible. "
            "The head, shoulders, torso, hair, hand, and required state prop must tilt diagonally inward toward the frame, matching a side-peek pose. "
            "Do not show a complete front-facing standing body. Do not place the character outside/left of the left boundary."
        )
    if is_edge_state(state, "right"):
        return (
            "Right edge state source art: do not draw any black screen-edge line, guide line, border, or vertical separator in the source sheet. "
            "Pose the character as if peeking inward from behind an invisible right screen edge: the character must appear on the left side of that right boundary. "
            "Most of the body remains hidden behind/off-screen at the right boundary, with only 35-55 percent of the body width visible. "
            "The head, shoulders, torso, hair, hand, and required state prop must tilt diagonally inward toward the frame, matching a side-peek pose. "
            "Do not show a complete front-facing standing body. Do not place the character outside/right of the right boundary."
        )
    return "Normal state: no screen-edge line; keep the whole character and intended props fully inside each frame slot."


def state_material_rule(state: str) -> str:
    if "success" in state:
        return (
            "Success sign material: draw a white or very light placard board held by the character, with one bold emerald green check mark on the board. "
            "The check mark must be clearly inside the board, separated from the chroma background, and there must be no readable text."
        )
    if "rejected" in state or state == "failed":
        return (
            "Failure sign material: draw a white or very light placard board held by the character, with one bold red X mark on the board. "
            "The X mark must be clearly inside the board, separated from the chroma background, and there must be no readable text."
        )
    return "State material: keep all character details and props in non-chroma colors, with opaque clean edges."


def identity_for_state(spec: dict, kind: str, state: str) -> str:
    if allows_original_prop(kind, state):
        return spec["identity"]
    return spec["no_prop_identity"]


def allows_original_prop(kind: str, state: str) -> bool:
    return kind == "extra-state" and (state == "idle-normal" or state.startswith("edge-idle-normal"))


def prop_rule(kind: str, state: str) -> str:
    if allows_original_prop(kind, state):
        return "Prop rule: this idle-normal state may keep the character's original gun or umbrella prop."
    if state == "coding" or state.startswith("edge-coding"):
        return (
            "Prop rule: a compact laptop computer is allowed for this coding state. "
            "Do not draw any gun, umbrella, rifle, staff, sheath, charm-on-handle, long horizontal stick, "
            "or weapon-like long horizontal prop."
        )
    return (
        "Prop rule: do not draw any gun, umbrella, rifle, staff, sheath, charm-on-handle, long horizontal stick, long horizontal black bar, "
        "or long horizontal white-blue prop in this state."
    )


def grid_layout(frame_count: int) -> tuple[int, int]:
    if frame_count <= 0:
        raise ValueError(f"frame_count must be positive, got {frame_count}")
    if frame_count == 12:
        return 4, 3
    columns = max(1, math.ceil(math.sqrt(frame_count * 4 / 3)))
    rows = math.ceil(frame_count / columns)
    return columns, rows


def is_sleep_state(state: str) -> bool:
    return "sleep" in state


def face_rule(state: str) -> str:
    if is_sleep_state(state):
        return (
            "Face rule: keep the eyes closed in every frame as one stable sleeping expression; do not animate a blink, wink, eye opening, "
            "or squeezed-eye change. Keep the mouth small and closed in every frame; no open mouth, O-mouth, shout, gasp, or sudden smile change."
        )
    return (
        "Face rule: keep the visible eye or both eyes open and steady in every frame. Do not draw any blink, wink, squeezed-shut eye, "
        "closed-eye reaction frame, open mouth, O-mouth, shout, gasp, or sudden smile change. Keep one small closed mouth shape consistent across the strip."
    )


def prompt_for(character_id: str, spec: dict, kind: str, state: str, frame_count: int, action: str, loop: bool) -> str:
    loop_rule = "The first and last frames must match cleanly for a loop." if loop else "This state does not need to loop, but must still use the configured frame count."
    key_color = spec["key_color"]
    key_label = spec["key_label"]
    source_anchor = "source-magenta.png" if key_color == "#FF00FF" else "source-green.png"
    columns, rows = grid_layout(frame_count)
    slot_count = columns * rows
    unused_slot_rule = ""
    if slot_count > frame_count:
        unused_slot_rule = f" Leave the final {slot_count - frame_count} unused slot(s) as untouched flat chroma-key {key_label}."
    return f"""Use case: stylized-concept
Asset type: OpenPlana neo desktop pet action source strip
Primary request: Create an exact {frame_count}-frame chroma-key sprite source sheet for {character_id}, state {state}, arranged as a {columns} columns x {rows} rows grid. The whole source image must match the {columns}:{rows} grid aspect ratio, not square unless the grid is square. There must be exactly {frame_count} occupied equal square frame slots, read left to right, top to bottom.{unused_slot_rule} Do not draw grid lines, labels, numbers, or borders.
Reference images: use {spec['reference']} as the original standing character reference; use shared/Characters/{character_id}/qa/{source_anchor} as the generated Q-version identity anchor for this run.
Character identity: {identity_for_state(spec, kind, state)}
Chibi style: compact 3-head Q-version desktop pet, clean anime sprite linework, soft but crisp shading, readable at 256x256.
Action: {action}.
Schema: kind={kind}; state={state}; frame_count={frame_count}; frame_duration=0.1666666667; loop={str(loop).lower()}.
Timing: {loop_rule} Adjacent frames must transition naturally.
{face_rule(state)}
Scene/backdrop: every empty pixel in every slot and every gutter between slots must be perfectly flat solid chroma-key {key_label}, exact {key_color}, with no gradients, no texture, no shadows, no glow, no lighting variation.
Slot isolation: keep every frame completely isolated in its own square slot. Leave clean chroma-key gaps between all slots. No character pixels, halo pixels, prop pixels, antialiasing, top fragments, bottom fragments, horizontal marks, or edge guide lines may cross from one slot into another.
Halo rule: {spec['halo']} Every pixel visible through the halo opening must be exact {key_color} in the source strip.
Composition/framing: exactly {frame_count} complete poses in the configured grid. One complete character per occupied slot. Keep generous chroma-key padding around each character inside its slot. No overlap between slots. Each generated frame must already fit a 1:1 256x256 square frame before local processing.
Side rule: {side_rule(state)}
{prop_rule(kind, state)}
Material rule: {state_material_rule(state)}
Safety: full-body and normal frames need at least 8px safe padding on all sides. Edge frames keep only the black edge line on the dock side; top, bottom, and opposite side need at least 8px safe padding.
Avoid: fewer than {frame_count} frames, more than {frame_count} frames, merged frames, duplicate missing slots, back view, rear view, turned-away carried pose, blink, wink, closed-eye frame in non-sleep states, sudden open mouth, O-mouth, shout, gasp, white background, checkerboard, text, watermark, readable UI text, frame numbers, guide marks, scenery, shadows, glow, motion blur, speed lines, floating effects, cropped halo, cropped hair, cropped hands, cropped props, white or opaque halo center, filled halo interior, touching adjacent frame slots, changing face width, changing head silhouette, large size jumps between adjacent frames.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=pathlib.Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-atlas", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    actions = []

    for character_id, spec in CHARACTERS.items():
        if args.include_atlas:
            for row_index, (state, action) in enumerate(ATLAS_ROWS):
                frame_count = 12
                prompt = prompt_for(character_id, spec, "atlas-row", state, frame_count, action, True)
                actions.append({
                    "character": character_id,
                    "kind": "atlas-row",
                    "state": state,
                    "row": row_index,
                    "frameCount": frame_count,
                    "frameDuration": 0.1666666667,
                    "loop": True,
                    "promptPath": f".codex/tmp/neo-pets/prompts/{character_id}/atlas-row/{state}.md",
                    "sourceStripPath": f".codex/tmp/neo-pets/generated/{character_id}/atlas-row/{state}/source-strip-chroma.png",
                    "sourceGridPath": f".codex/tmp/neo-pets/generated/{character_id}/atlas-row/{state}/source-grid-chroma.png",
                    "prompt": prompt,
                })

        for state, config in schema.get("extraStates", {}).items():
            frame_paths = config.get("framePaths", [])
            frame_count = len(frame_paths)
            loop = bool(config.get("loop", True))
            action = EXTRA_ACTIONS[state]
            prompt = prompt_for(character_id, spec, "extra-state", state, frame_count, action, loop)
            actions.append({
                "character": character_id,
                "kind": "extra-state",
                "state": state,
                "frameCount": frame_count,
                "frameDuration": float(config.get("frameDuration", 0.1666666667)),
                "loop": loop,
                "framePaths": frame_paths,
                "promptPath": f".codex/tmp/neo-pets/prompts/{character_id}/extra-state/{state}.md",
                "sourceStripPath": f".codex/tmp/neo-pets/generated/{character_id}/extra-state/{state}/source-strip-chroma.png",
                "sourceGridPath": f".codex/tmp/neo-pets/generated/{character_id}/extra-state/{state}/source-grid-chroma.png",
                "prompt": prompt,
            })

    out = {
        "schemaSource": str(args.schema),
        "characters": list(CHARACTERS),
        "actions": actions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for action in actions:
        prompt_path = ROOT / action["promptPath"]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(action["prompt"], encoding="utf-8")
        del action["prompt"]
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    print(f"actions={len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
