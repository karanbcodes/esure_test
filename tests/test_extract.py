from policy_etl.extract import discover_input_files, extract_raw_events


def test_discover_input_files(temp_jsonl_dir):
    files = discover_input_files(temp_jsonl_dir)
    assert len(files) == 1


def test_extract_raw_events_counts(temp_jsonl_dir):
    raw = extract_raw_events(temp_jsonl_dir)
    assert len(raw) == 3
    assert "_source_file" in raw.columns
