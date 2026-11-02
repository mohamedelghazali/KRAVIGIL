#!/bin/bash

set -e

echo "[*] Building KRAVIGIL CLI..."

mkdir -p dist

pip install pyinstaller tabulate requests

pyinstaller --onefile --name kravigil cli/kravigil.py

mv dist/kravigil dist/kravigil-cli

echo "[+] CLI built successfully at dist/kravigil-cli"
echo "[*] Run it using: ./dist/kravigil-cli --help"
