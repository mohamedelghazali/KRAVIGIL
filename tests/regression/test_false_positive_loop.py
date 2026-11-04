from backend.services.correlation.deduplication import merge_duplicate_findings


def test_repeated_scan_does_not_reopen_rejected_false_positive():
    merged = merge_duplicate_findings(
        [
            {
                "vulnerability_key": "scanner:known-false-positive",
                "severity": "medium",
                "validation_status": "potential",
                "workflow_status": "open",
                "evidence_refs": ["evidence://first"],
            },
            {
                "vulnerability_key": " SCANNER:KNOWN-FALSE-POSITIVE ",
                "severity": "high",
                "validation_status": "rejected",
                "workflow_status": "open",
                "evidence_refs": ["evidence://second"],
            },
        ]
    )

    assert len(merged) == 1
    assert merged[0]["validation_status"] == "rejected"
    assert merged[0]["severity"] == "high"
    assert merged[0]["evidence_refs"] == [
        "evidence://first",
        "evidence://second",
    ]
