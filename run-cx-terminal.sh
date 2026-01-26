#!/bin/bash
# CX Terminal: Run with proper app bundle for correct dock icon
set -e

cd "$(dirname "$0")"

BUILD_TYPE=${1:-release}
APP_BUNDLE="assets/macos/CX Terminal.app"

echo "Setting up CX Terminal app bundle..."

# Copy binary to app bundle
mkdir -p "$APP_BUNDLE/Contents/MacOS"
cp "target/$BUILD_TYPE/cx-terminal-gui" "$APP_BUNDLE/Contents/MacOS/"

# Copy other binaries if they exist
for bin in cx-terminal wezterm-mux-server strip-ansi-escapes; do
  if [[ -f "target/$BUILD_TYPE/$bin" ]]; then
    cp "target/$BUILD_TYPE/$bin" "$APP_BUNDLE/Contents/MacOS/"
  fi
done

echo "Launching CX Terminal..."
open "$APP_BUNDLE"
