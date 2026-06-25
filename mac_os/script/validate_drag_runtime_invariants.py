#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PET_WINDOW = ROOT / "Sources" / "OpenPlana" / "Services" / "PetWindowController.swift"
PET_OVERLAY = ROOT / "Sources" / "OpenPlana" / "Views" / "PetOverlayView.swift"
APP_MODEL = ROOT / "Sources" / "OpenPlana" / "Stores" / "AppModel.swift"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=pathlib.Path)
    parser.add_argument("--summary", action="store_true")
    return parser.parse_args()


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def block(text: str, start_pattern: str, end_pattern: str | None = None) -> str:
    start = re.search(start_pattern, text)
    if not start:
        return ""
    if end_pattern is None:
        return text[start.start():]
    end = re.search(end_pattern, text[start.end():])
    if not end:
        return text[start.start():]
    return text[start.start():start.end() + end.start()]


def add_check(checks: list[dict[str, object]], check_id: str, ok: bool, detail: str, file: pathlib.Path) -> None:
    checks.append({
        "id": check_id,
        "ok": ok,
        "file": str(file.relative_to(ROOT)),
        "detail": detail,
    })


def main() -> int:
    args = parse_args()
    pet_window = read(PET_WINDOW)
    pet_overlay = read(PET_OVERLAY)
    app_model = read(APP_MODEL)
    checks: list[dict[str, object]] = []

    mouse_dragged = block(
        pet_window,
        r"override func mouseDragged\(with event: NSEvent\)",
        r"override func mouseUp\(with event: NSEvent\)",
    )
    mouse_up = block(
        pet_window,
        r"override func mouseUp\(with event: NSEvent\)",
        r"private var interactiveBounds",
    )
    prepare = block(
        pet_window,
        r"func prepareForDragging\(spritePoint: NSPoint\? = nil, at screenPoint: NSPoint\? = nil, animated: Bool\)",
        r"func updateDockPreview",
    )
    sprite_offset = block(
        pet_overlay,
        r"private var spriteEdgeOffset: CGFloat",
        r"\n}\n\nstruct ResizeHandleOverlay",
    )
    hosted_offset = block(
        pet_window,
        r"private func hostedContentOffset\(scale: CGFloat\)",
        r"private func windowFrameSize",
    )
    begin_dragging = block(
        app_model,
        r"func beginDragging\(\)",
        r"func triggerClick\(\)",
    )
    bind_model = block(
        pet_window,
        r"private func bindModel\(\)",
        r"private func configureForAllSpaces",
    )

    compact_dragged = compact(mouse_dragged)
    compact_prepare = compact(prepare)
    compact_mouse_up = compact(mouse_up)
    compact_sprite_offset = compact(sprite_offset)
    compact_hosted_offset = compact(hosted_offset)
    compact_begin_dragging = compact(begin_dragging)
    compact_bind_model = compact(bind_model)

    add_check(
        checks,
        "drag-window-follows-pointer-anchor",
        "if let dragAnchorInWindow" in mouse_dragged
        and "window.setFrameOrigin" in mouse_dragged
        and "x: current.x - dragAnchorInWindow.x" in mouse_dragged
        and "y: current.y - dragAnchorInWindow.y" in mouse_dragged,
        "mouseDragged should move the window from the fixed pointer anchor while dragging",
        PET_WINDOW,
    )
    add_check(
        checks,
        "drag-start-keeps-pointer-anchor-on-sprite",
        "controller.prepareForDragging(spritePoint: pointInSprite, at: current, animated: false)" in compact_dragged
        and compact_dragged.find("controller.prepareForDragging(spritePoint: pointInSprite, at: current, animated: false)")
        < compact_dragged.find("model.beginDragging()"),
        "edge drag start should expand/reposition before isDragging flips so the original sprite point stays under the pointer",
        PET_WINDOW,
    )
    add_check(
        checks,
        "prepare-clears-hidden-content-offset",
        "dragView.contentOffsetX = 0" in prepare,
        "prepareForDragging should clear hosted content offset before floating drag",
        PET_WINDOW,
    )
    add_check(
        checks,
        "prepare-repositions-from-sprite-anchor",
        "x = screenPoint.x - spriteX - spritePoint.x" in prepare
        and "y = screenPoint.y - spritePoint.y" in prepare
        and "isDocked: false" in prepare,
        "prepareForDragging should compute floating frame origin from the clicked sprite point",
        PET_WINDOW,
    )
    add_check(
        checks,
        "drag-state-disables-docked-offset",
        "guard !model.isDragging, model.isDockedToEdge else { return 0 }" in compact_sprite_offset,
        "SwiftUI sprite edge offset should be zero while dragging",
        PET_OVERLAY,
    )
    add_check(
        checks,
        "drag-state-disables-hosted-offset",
        "guard model.isDockedToEdge, !model.isDragging else { return 0 }" in compact_hosted_offset,
        "AppKit hosted content offset should be zero while dragging",
        PET_WINDOW,
    )
    add_check(
        checks,
        "begin-dragging-clears-edge-state",
        "edgeRevealProgress = 1" in begin_dragging
        and "isDockedToEdge = false" in begin_dragging
        and "isDragging = true" in begin_dragging,
        "beginDragging should leave edge state before the carried animation is shown",
        APP_MODEL,
    )
    add_check(
        checks,
        "dock-side-binding-does-not-dock-while-dragging",
        "guard self?.model.isDragging == false else { return }" in compact_bind_model,
        "dockSide changes should not auto-dock while the user is dragging",
        PET_WINDOW,
    )
    add_check(
        checks,
        "release-only-docking",
        re.search(r"controller\.dock\(animated:\s*false", mouse_up) is not None
        and "model.isDragging = false" in mouse_up
        and re.search(r"controller\.dock\(animated:\s*false", mouse_dragged) is None,
        "edge docking should happen on mouseUp, not during mouseDragged",
        PET_WINDOW,
    )
    add_check(
        checks,
        "drag-updates-edge-preview",
        "updateDockPreview(for: current" in mouse_dragged,
        "mouseDragged should update the edge drop preview before release",
        PET_WINDOW,
    )
    add_check(
        checks,
        "preview-renderer-exists",
        re.search(r"func showDockPreview\(frame: NSRect\)", pet_window) is not None,
        "edge drop preview renderer should exist",
        PET_WINDOW,
    )
    add_check(
        checks,
        "preview-is-20-percent-black-rounded-rect",
        (
            re.search(r"func showDockPreview\(frame: NSRect\)", pet_window) is not None
            and (
                "opacity(0.2)" in pet_window
                or "alphaValue = 0.2" in pet_window
                or "withAlphaComponent(0.2)" in pet_window
            )
            and ("RoundedRectangle" in pet_window or "cornerRadius" in pet_window)
        ),
        "edge drop preview should be a 20% black rounded rectangle",
        PET_WINDOW,
    )

    failures = [check for check in checks if not check["ok"]]
    result = {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "humanVerificationRequired": [
            "Confirm the cursor remains visually over the same sprite point when starting a drag from a docked edge.",
            "Confirm only the edge drop preview is visible before mouseUp; the docked offset should not apply until release.",
        ],
    }

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.summary:
        print(f"ok={str(result['ok']).lower()}")
        for check in checks:
            status = "ok" if check["ok"] else "fail"
            print(f"{status}\t{check['id']}\t{check['file']}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
