"""生成 100 条合成线索（含 15 重复），确定性、可复现。无真实个人信息。"""
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AREAS = ["浦东张江镇", "徐汇徐家汇街道", "静安南京西路", "闵行莘庄镇", "浦东金桥镇"]
CHANNELS = ["channel_a", "channel_b", "channel_c"]


def build_rows():
    rows = []
    # 85 unique: 13800000000 .. 13800000084
    for i in range(85):
        phone = f"1380000{i:04d}"
        rows.append({
            "phone": phone,
            "area_text": AREAS[i % len(AREAS)],
            "source_channel": CHANNELS[i % len(CHANNELS)],
            "station_id": "",
            "job_type": "undecided",
        })
    # 15 duplicates of earlier phones, with normalization variants
    for j in range(15):
        base = f"1380000{j:04d}"          # 与前 15 条重复
        if j % 3 == 0:
            phone = f"+86 {base}"          # +86 前缀 + 空格
        elif j % 3 == 1:
            phone = f"{base[:3]}-{base[3:7]}-{base[7:]}"  # 连字符
        else:
            phone = f"86{base}"            # 86 前缀
        rows.append({
            "phone": phone,
            "area_text": AREAS[j % len(AREAS)],
            "source_channel": "channel_dup",
            "station_id": "",
            "job_type": "undecided",
        })
    return rows


def main():
    out = Path(__file__).resolve().parents[1] / "tests" / "data" / "leads_100.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["phone", "area_text", "source_channel", "station_id", "job_type"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
