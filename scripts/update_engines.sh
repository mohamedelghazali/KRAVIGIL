#!/bin/bash

set -e

echo "[*] Updating KRAVIGIL scanning engines..."

if command -v nuclei &> /dev/null; then
    echo "[*] Updating Nuclei templates..."
    nuclei -update-templates
else
    echo "[!] Nuclei not found. Skipping."
fi

if command -v semgrep &> /dev/null; then
    echo "[*] Updating Semgrep rules..."
    semgrep --update
else
    echo "[!] Semgrep not found. Skipping."
fi

if command -v trivy &> /dev/null; then
    echo "[*] Updating Trivy vulnerability DB..."
    trivy image --download-db-only
else
    echo "[!] Trivy not found. Skipping."
fi

echo "[*] Engines updated successfully."
