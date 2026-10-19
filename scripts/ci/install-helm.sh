#!/usr/bin/env bash
set -euo pipefail
archive=helm-v4.3.1-linux-amd64.tar.gz
mkdir -p .local/ci-tools
cd .local/ci-tools
curl -fsSL "https://get.helm.sh/$archive" -o "$archive"
curl -fsSL "https://get.helm.sh/$archive.sha256sum" -o "$archive.sha256sum"
sha256sum --check "$archive.sha256sum"
tar -xzf "$archive"
echo "$PWD/linux-amd64" >> "$GITHUB_PATH"
