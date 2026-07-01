from jemscrape.dedup import collapse_stock, pick_price, collapse_variants
from jemscrape.canonical import CanonicalRecord


def _rec(pid, list_price):
    return CanonicalRecord(
        source_site="e", source_url="u", scraped_at="t", authorization_ref="a",
        product_id=pid, sku=pid, name="n", brand="b", description_raw="", description_clean="",
        breadcrumbs=[], division="", category_path="", images=[], specs={},
        prices=[], list_price=list_price, cost_price=None, variants=[],
        stock={}, attachments=[], related=[], raw_ref="",
    )


HUB = {"hub-real", "hub-mirror-1", "hub-mirror-2"}


def test_collapse_stock_collapses_hub_to_max_and_sums_others():
    by_loc = {"hub-real": 10, "hub-mirror-1": 10, "hub-mirror-2": 8,
              "leeds": 3, "ireland": 4}
    out = collapse_stock(by_loc, hub_group=HUB, ireland_branch="ireland")
    assert out["uk"] == 13      # max(10,10,8)=10 hub + 3 leeds
    assert out["ireland"] == 4
    assert out["total"] == 17


def test_collapse_stock_clamps_negative_oversold():
    by_loc = {"leeds": -5, "ireland": 2}
    out = collapse_stock(by_loc, hub_group=HUB, ireland_branch="ireland")
    assert out["uk"] == 0       # -5 clamped to 0
    assert out["total"] == 2


def test_pick_price_prefers_contract_band():
    prices = [{"band": "universal", "value": 10}, {"band": "PLE-J015", "value": 9}]
    assert pick_price(prices, band_priority=["PLE-J015", "universal"])["value"] == 9


def test_pick_price_falls_back_to_first_when_no_band_matches():
    prices = [{"band": "x", "value": 5}, {"band": "y", "value": 6}]
    assert pick_price(prices, band_priority=["PLE-J015"])["value"] == 5


def test_pick_price_none_when_empty():
    assert pick_price([], band_priority=["PLE-J015"]) is None


def test_collapse_variants_keeps_cheapest_and_marks_multi():
    records = [_rec("M1", 20.0), _rec("M1", 15.0), _rec("M2", 8.0)]
    out = collapse_variants(records)
    by_pid = {r.product_id: r for r in out}
    assert len(out) == 2
    assert by_pid["M1"].list_price == 15.0
    assert getattr(by_pid["M1"], "multi_variant", False) is True
    assert getattr(by_pid["M2"], "multi_variant", False) is False


def test_collapse_variants_none_list_price_is_infinity():
    records = [_rec("M1", None), _rec("M1", 12.0)]
    out = collapse_variants(records)
    assert out[0].list_price == 12.0   # the priced one wins over None
