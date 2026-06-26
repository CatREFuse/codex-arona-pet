#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="OpenPlana"
BUNDLE_ID="dev.tanshow.OpenPlana"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
APP_ICON="$ROOT_DIR/Sources/OpenPlana/Resources/AppIcon.icns"
SHARED_CHARACTERS_DIR="$ROOT_DIR/../shared/Characters"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

swift build
"$ROOT_DIR/script/validate_pet_assets.py" --character plana --character plana-cat-maid --character arona --character arona-swimsuit --character kotonoha-neo

BUILD_DIR="$(swift build --show-bin-path)"
BUILD_BINARY="$BUILD_DIR/$APP_NAME"
RESOURCE_BUNDLE="$BUILD_DIR/OpenPlana_OpenPlana.bundle"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"

if [ -d "$RESOURCE_BUNDLE" ]; then
  cp -R "$RESOURCE_BUNDLE" "$APP_RESOURCES/"
fi

if [ ! -d "$SHARED_CHARACTERS_DIR" ]; then
  echo "missing shared characters: $SHARED_CHARACTERS_DIR" >&2
  exit 1
fi
mkdir -p "$APP_RESOURCES/shared"
rm -rf "$APP_RESOURCES/shared/Characters"
cp -R "$SHARED_CHARACTERS_DIR" "$APP_RESOURCES/shared/Characters"

if [ ! -f "$APP_ICON" ]; then
  echo "missing app icon: $APP_ICON" >&2
  exit 1
fi
cp "$APP_ICON" "$APP_RESOURCES/AppIcon.icns"

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

CHARACTER_LIST="$(OPEN_PLANA_ROOT="$ROOT_DIR" "$APP_BINARY" --list-characters)"
EXPECTED_CHARACTER_LIST=$'plana\t普拉娜\narona\t阿罗娜\nplana-cat-maid\t普拉娜（女仆）\narona-swimsuit\t阿罗娜（泳装）\nkotonoha-neo\t言叶'
ACTUAL_CHARACTER_LIST="$(printf '%s\n' "$CHARACTER_LIST" | cut -f1,2)"
if [ "$ACTUAL_CHARACTER_LIST" != "$EXPECTED_CHARACTER_LIST" ]; then
  printf 'unexpected characters:\n%s\n' "$CHARACTER_LIST" >&2
  exit 1
fi

open_app() {
  OPEN_PLANA_ROOT="$ROOT_DIR" /usr/bin/open -n "$APP_BUNDLE"
  sleep 0.5
  /usr/bin/osascript <<'APPLESCRIPT' >/dev/null 2>&1 || true
tell application "System Events"
  tell process "OpenPlana"
    set frontmost to true
    repeat with candidateWindow in windows
      set candidateSize to size of candidateWindow
      if item 1 of candidateSize > 500 then
        perform action "AXRaise" of candidateWindow
        exit repeat
      end if
    end repeat
  end tell
end tell
APPLESCRIPT
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    OPEN_PLANA_ROOT="$ROOT_DIR" lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    OPEN_PLANA_ROOT="$ROOT_DIR" "$APP_BINARY" --verify-animations plana plana-cat-maid arona arona-swimsuit kotonoha-neo
    open_app
    sleep 2
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
