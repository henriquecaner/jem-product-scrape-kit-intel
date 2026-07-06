import csv
import json

import build_dataset
from build_dataset import build


def _raw(pid, name, crumbs, by_loc, list_price):
    return {
        "url": f"https://e/p/{pid}", "raw_ref": f"data/{pid}.html",
        "raw": {"sku": pid, "name": name, "breadcrumbs": crumbs,
                "list_price": list_price,
                "prices": [{"value": 9.9, "band": "universal"},
                           {"value": 9.0, "band": "PLE-J015"}],
                "stock": {"by_location": by_loc}},
    }


HUB = {"hub", "hub-mirror"}


def test_build_normalizes_dedups_and_exports(tmp_path):
    exports = tmp_path / "exports"
    raws = [
        _raw("M1", "Widget", ["Fire", "Detectors"], {"hub": 5, "hub-mirror": 5, "ie": 2}, 20.0),
        _raw("M1", "Widget v2", ["Fire", "Detectors"], {"hub": 5, "hub-mirror": 5, "ie": 2}, 15.0),
        _raw("M2", "Gadget", ["Fire"], {"leeds": 3}, 8.0),
    ]
    summary = build(
        raws, source_site="e", authorization_ref="auth-1", scraped_at="t",
        exports_dir=exports, band_priority=["PLE-J015", "universal"],
        hub_group=HUB, ireland_branch="ie",
    )
    assert summary["normalized"] == 3
    assert summary["exported"] == 2       # M1 variants collapsed to 1

    with (exports / "products.csv").open(newline="", encoding="utf-8") as f:
        rows = {r["product_id"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"M1", "M2"}
    assert rows["M1"]["best_price"] == "9.0"       # PLE-J015 band chosen
    assert rows["M1"]["list_price"] == "15.0"      # cheaper variant kept
    assert rows["M1"]["total_stock"] == "7"        # hub max 5 + ie 2
    assert (exports / "wiki" / "INDEX.md").exists()


def test_build_handles_empty(tmp_path):
    summary = build([], source_site="e", authorization_ref="a", scraped_at="t",
                    exports_dir=tmp_path / "exports")
    assert summary["normalized"] == 0 and summary["exported"] == 0
    assert (tmp_path / "exports" / "products.csv").exists()


def test_main_success_writes_exports(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text(json.dumps([
        _raw("M1", "Widget", ["Fire"], {"leeds": 3}, 10.0),
    ]), encoding="utf-8")
    out_dir = tmp_path / "exports"

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(out_dir),
    ])

    assert rc == 0
    assert (out_dir / "products.csv").exists()
    assert (out_dir / "wiki").exists()


def test_main_missing_config_returns_2_no_traceback(tmp_path, capsys):
    recs_path = tmp_path / "records.json"
    recs_path.write_text("[]", encoding="utf-8")
    missing_cfg = tmp_path / "does_not_exist.json"

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(missing_cfg),
        "--exports", str(tmp_path / "exports"),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "config" in captured.err.lower()


def test_main_missing_target_domain_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"runtime": "local"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text("[]", encoding="utf-8")

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "target_domain" in captured.err.lower()


def test_main_records_file_not_a_list_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "records" in captured.err.lower()


def test_main_missing_records_file_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    missing_recs = tmp_path / "does_not_exist.json"

    rc = build_dataset.main([
        "--records", str(missing_recs),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""


def test_build_skips_malformed_record(tmp_path):
    import build_dataset
    raws = [
        {"url": "https://x/1", "raw": {"sku": "A", "product_id": "A", "name": "Good"}},
        {"url": "https://x/2", "raw": {"sku": "", "product_id": "", "name": ""}},  # falha validate()
    ]
    summary = build_dataset.build(
        raws, source_site="x", authorization_ref="ref",
        scraped_at="2026-07-06T00:00:00+00:00", exports_dir=str(tmp_path),
    )
    assert summary["normalize_errors"] == 1
    assert summary["normalized"] == 1


def test_build_skips_non_dict_record_without_crashing(tmp_path):
    raws = [
        "junk",  # não é dict: item["raw"] levanta TypeError, item.get(...) no handler não pode quebrar
        {"url": "https://x/1", "raw": {"sku": "A", "product_id": "A", "name": "Good"}},
    ]
    summary = build_dataset.build(
        raws, source_site="x", authorization_ref="ref",
        scraped_at="2026-07-06T00:00:00+00:00", exports_dir=str(tmp_path),
    )
    assert summary["normalize_errors"] == 1
    assert summary["normalized"] == 1
    assert summary["exported"] == 1


def test_build_propagates_category_map(tmp_path):
    import build_dataset
    raws = [{"url": "u", "raw": {"sku": "P", "product_id": "P", "name": "N",
                                 "breadcrumbs": ["A", "B"]}}]
    summary = build_dataset.build(
        raws, source_site="x", authorization_ref="r",
        scraped_at="t", exports_dir=str(tmp_path),
        category_map={"A > B": "Canon/Cat"},
    )
    csv_text = (tmp_path / "products.csv").read_text(encoding="utf-8")
    assert "Canon/Cat" in csv_text


def test_main_category_map_malformed_json_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text("[]", encoding="utf-8")
    bad_map = tmp_path / "category_map.json"
    bad_map.write_text("{not valid json", encoding="utf-8")

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
        "--category-map", str(bad_map),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "category map" in captured.err.lower()


def test_main_category_map_not_a_dict_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text("[]", encoding="utf-8")
    list_map = tmp_path / "category_map.json"
    list_map.write_text(json.dumps(["A > B", "C > D"]), encoding="utf-8")

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
        "--category-map", str(list_map),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "category map" in captured.err.lower()


def test_main_category_map_missing_file_returns_2_no_traceback(tmp_path, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"target_domain": "example.com"}), encoding="utf-8")
    recs_path = tmp_path / "records.json"
    recs_path.write_text("[]", encoding="utf-8")
    missing_map = tmp_path / "does_not_exist.json"

    rc = build_dataset.main([
        "--records", str(recs_path),
        "--config", str(cfg_path),
        "--exports", str(tmp_path / "exports"),
        "--category-map", str(missing_map),
    ])

    assert rc == 2
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert "category map" in captured.err.lower()


def test_extract_categories_cli(tmp_path):
    import build_dataset
    records = tmp_path / "raw.json"
    records.write_text(json.dumps(
        [{"url": "u", "raw": {"breadcrumbs": ["A", "B"]}}]), encoding="utf-8")
    out = tmp_path / "cats.json"
    rc = build_dataset.main([
        "--records", str(records), "--extract-categories", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["category_path"] == "A > B"
