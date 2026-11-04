"""08 tam 1b r2 MINOR-r2-4: the manifest's `text_filters` counts a file that failed before its
record was registered under `unregistered`, never under `none`; `none` is only a real record
without a `text_filter` (written before 19)."""

from ffcore.knowledge import raw_ingest


def test_08t_29_unregistered_files_have_their_own_bucket():
    report = raw_ingest.RawIngestReport(text_filter="pii_ner")
    report.files = [
        ("confluence/DEMO/1.md", "1" * 64, "confluence:DEMO"),
        ("confluence/DEMO/2.md", "2" * 64, "confluence:DEMO"),
        ("confluence/DEMO/3.md", "3" * 64, "confluence:DEMO"),
    ]
    report.current = {
        "confluence/DEMO/1.md": ("indexed", 4, "pii_ner@1"),
        "confluence/DEMO/2.md": ("indexed", 2, None),  # a record without a filter
    }
    report.unregistered = [("confluence:DEMO", "confluence/DEMO/3.md", "ValueError")]
    filters = report.manifest()["text_filters"]
    assert filters == {
        "none": {"documents": 1, "chunks": 2},
        "pii_ner@1": {"documents": 1, "chunks": 4},
        "unregistered": {"documents": 1, "chunks": 0},
    }
