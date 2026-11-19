"""AC1：100 条线索去重（手机号 token）+ 分配规则。"""
import csv
from pathlib import Path

from src.leads import Lead, import_leads
from src.vault import tokenize

DATA = Path(__file__).parent / "data" / "leads_100.csv"


def load_rows():
    with DATA.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_csv_has_100_rows():
    assert len(load_rows()) == 100


def test_dedup_85_inserted_15_skipped():
    rows = load_rows()
    leads = [Lead(r["phone"], r["area_text"], r["source_channel"],
                  r["station_id"] or None, r["job_type"]) for r in rows]
    res = import_leads(leads, rule="round_robin")
    assert res.inserted == 85
    assert res.duplicates_skipped == 15
    # 归一化变体（+86 / 连字符 / 86 前缀）应与原号同 token
    assert tokenize("phone", "+86 13800000000") == tokenize("phone", "13800000000")


def test_round_robin_balanced():
    rows = load_rows()
    leads = [Lead(r["phone"], r["area_text"], r["source_channel"], None, r["job_type"]) for r in rows]
    res = import_leads(leads, rule="round_robin", active_stations=["S1", "S2", "S3", "S4"])
    vals = sorted(res.assignments.values())
    assert sum(vals) == 85
    assert vals[-1] - vals[0] <= 1   # 21/21/21/22


def test_by_station_rule():
    leads = [Lead(f"1390000{i:04d}", "浦东张江镇", "ch", "S2") for i in range(5)]
    res = import_leads(leads, rule="by_station", active_stations=["S1", "S2"])
    assert res.assignments == {"S1": 0, "S2": 5}


def test_by_region_rule():
    leads = [
        Lead("13700000001", "浦东张江镇", "ch"),
        Lead("13700000002", "徐汇徐家汇街道", "ch"),
        Lead("13700000003", "静安南京西路", "ch"),
        Lead("13700000004", "闵行莘庄镇", "ch"),
    ]
    res = import_leads(leads, rule="by_region", active_stations=["S1", "S2", "S3", "S4"])
    assert res.assignments == {"S1": 1, "S2": 1, "S3": 1, "S4": 1}
