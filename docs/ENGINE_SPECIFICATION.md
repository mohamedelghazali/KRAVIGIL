# KRAVIGIL Engine Specification

## 1. Interface Contract

Every engine (C++, Python, or External Adapter) must implement the `BaseEngineAdapter` interface.

### 1.1 Execution
```python
def execute(self, args: List[str]) -> str:
```
- Must run the engine binary or script with provided arguments.
- Must enforce a strict `timeout_seconds`.
- Must return the raw `stdout` string if successful.
- Must raise `KravigilException` (code `ENGINE_EXECUTION_ERROR` or `ENGINE_TIMEOUT`) on failure.

### 1.2 Parsing
```python
def parse_output(self, raw_output: str) -> List[Dict[str, Any]]:
```
- Must parse `raw_output` into a list of normalized dictionaries.
- Must handle malformed output gracefully (logging a warning and continuing).

## 2. Unified Output Schema

The output dictionary from `parse_output` must conform to the following structure before being passed to the `Normalizer`:

```json
{
  "title": "String (e.g., SQL Injection)",
  "severity": "String (CRITICAL, HIGH, MEDIUM, LOW, INFO)",
  "description": "String",
  "cve_id": "String (optional)",
  "cwe_id": "String (optional)",
  "raw": {}
}
```

## 3. Engine Types

- **Network (C++)**: Uses gRPC. Streams `ScanEvent` messages.
- **Web (Nuclei)**: Uses `nuclei -json`. Parses `VULNERABILITY_FOUND`.
- **SAST (Semgrep)**: Uses `semgrep --json`. Parses `CODE_VULNERABILITY`.
- **Secrets (Gitleaks)**: Uses `gitleaks detect`. Parses `SECRET_FOUND`.
- **Container (Trivy)**: Uses `trivy image`. Parses `CONTAINER_VULNERABILITY`.
