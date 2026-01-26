#!/bin/bash
# CX Terminal: Create DMG installer for macOS
# Usage: ./ci/create-dmg.sh [release|debug]

set -e

BUILD_TYPE=${1:-release}
VERSION=$(grep '^version' wezterm-gui/Cargo.toml | head -1 | sed 's/version = "\(.*\)"/\1/')

echo "Creating CX Terminal DMG (version $VERSION, build: $BUILD_TYPE)"

# Paths
APP_NAME="CX Terminal"
APP_BUNDLE="CX Terminal.app"
DMG_NAME="CXTerminal-$VERSION-macos.dmg"
BUILD_DIR="build_dmg"
TARGET_DIR="target/$BUILD_TYPE"

# Clean up
rm -rf "$BUILD_DIR" "$DMG_NAME"
mkdir -p "$BUILD_DIR"

# Copy app template
echo "Copying app bundle..."
cp -r "assets/macos/CX Terminal.app" "$BUILD_DIR/$APP_BUNDLE"

# Copy binaries
echo "Copying binaries..."
mkdir -p "$BUILD_DIR/$APP_BUNDLE/Contents/MacOS"

for bin in cx-terminal cx-terminal-gui wezterm-mux-server strip-ansi-escapes; do
  if [[ -f "$TARGET_DIR/$bin" ]]; then
    cp "$TARGET_DIR/$bin" "$BUILD_DIR/$APP_BUNDLE/Contents/MacOS/"
    echo "  - $bin"
  else
    echo "  - $bin (not found, skipping)"
  fi
done

# Copy shell integration
echo "Copying shell integration..."
mkdir -p "$BUILD_DIR/$APP_BUNDLE/Contents/Resources"
cp -r assets/shell-integration/* "$BUILD_DIR/$APP_BUNDLE/Contents/Resources/" 2>/dev/null || true
cp -r assets/shell-completion "$BUILD_DIR/$APP_BUNDLE/Contents/Resources/" 2>/dev/null || true

# Generate terminfo
if command -v tic &> /dev/null; then
  echo "Generating terminfo..."
  tic -xe wezterm -o "$BUILD_DIR/$APP_BUNDLE/Contents/Resources/terminfo" termwiz/data/wezterm.terminfo 2>/dev/null || true
fi

# Add Applications symlink for drag-to-install
ln -s /Applications "$BUILD_DIR/Applications"

# Create DMG
echo "Creating DMG..."
hdiutil create -volname "$APP_NAME" -srcfolder "$BUILD_DIR" -ov -format UDZO "$DMG_NAME"

# Clean up
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Created: $DMG_NAME"
echo ""
echo "To install: Open the DMG and drag CX Terminal to Applications"
echo ""
echo "Note: For distribution, you'll need to:"
echo "  1. Code sign with: codesign --deep --sign 'Developer ID' '$APP_BUNDLE'"
echo "  2. Notarize with: xcrun notarytool submit '$DMG_NAME' ..."
echo "  3. Staple with: xcrun stapler staple '$DMG_NAME'"
