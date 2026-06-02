#!/usr/bin/env bash
# Build a Retitle.app bundle from the Swift package.
#
# Output: ./Retitle.app — a menu-bar Mac app (LSUIElement = true). It does
# not bring a Dock icon up and does not appear in ⌘-Tab. Quit from the
# menu bar dropdown.
#
# Requirements: Swift 5.9+ from either full Xcode or just the Command Line
# Tools (xcode-select --install).

set -euo pipefail

cd "$(dirname "$0")"
APP="Retitle.app"
CONFIG=${CONFIG:-release}

echo "-> swift build (-c ${CONFIG})"
swift build -c "${CONFIG}"

BIN="$(swift build -c "${CONFIG}" --show-bin-path)/Retitle"
if [[ ! -x "${BIN}" ]]; then
    echo "[x] build output missing: ${BIN}" >&2
    exit 1
fi

echo "-> assembling ${APP}"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS"
mkdir -p "${APP}/Contents/Resources"

cp "${BIN}" "${APP}/Contents/MacOS/Retitle"
cp Resources/Info.plist "${APP}/Contents/Info.plist"

# SPM emits the resource bundle alongside the binary; copy it inside.
BUILD_DIR="$(dirname "${BIN}")"
BUNDLE="${BUILD_DIR}/Retitle_Retitle.bundle"
if [[ -d "${BUNDLE}" ]]; then
    cp -R "${BUNDLE}" "${APP}/Contents/Resources/"
fi

# Also place .lproj dirs at the bundle top level so NSLocalizedString finds them
# whether or not the resource bundle is consulted first.
for lproj in Sources/Retitle/Resources/*.lproj; do
    [[ -d "${lproj}" ]] || continue
    cp -R "${lproj}" "${APP}/Contents/Resources/"
done

# Ad-hoc codesign so Gatekeeper at least lets the user open it via right-click.
codesign --force --deep --sign - "${APP}" >/dev/null 2>&1 || true

echo "[ok] built ${APP}"
echo
echo "Run with:"
echo "    open \"$(pwd)/${APP}\""
echo "Or drag into /Applications and launch from there."
