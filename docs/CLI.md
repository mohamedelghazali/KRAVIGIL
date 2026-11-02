# KRAVIGIL CLI Guide

The `kravigil-cli` tool allows you to interact with the platform directly from your terminal.

## Installation
```bash
pip install tabulate requests
python cli/kravigil.py --help
```
Or build the binary:
```bash
./scripts/build_cli.sh
./dist/kravigil-cli --help
```

## Commands

### 1. Login
```bash
kravigil-cli login --email admin@kravigil.local
```

### 2. Manage Targets
```bash
# List targets
kravigil-cli list-targets

# Create a new target
kravigil-cli create-target --name "Prod Server" --ip 10.0.0.5 --authorized
```

### 3. Start a Scan
```bash
kravigil-cli scan <TARGET_ID> --type network --ports 22,80,443
kravigil-cli scan <TARGET_ID> --type web
```

### 4. View Findings
```bash
# List all findings
kravigil-cli findings

# List only critical findings
kravigil-cli findings --severity CRITICAL
```
