import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.extract import extract, missing_fields  # noqa: E402

DATA = ROOT / "data" / "symptoms.csv"


def check(row, result):
    """정답과 다른 점을 문장 목록으로 돌려준다. 비어 있으면 통과다."""
    problems = []
    expected_intake = row["type"] == "intake"
    if result["is_intake"] != expected_intake:
        got = "intake" if result["is_intake"] else "off_topic"
        problems.append(f"type: 정답 {row['type']}, 결과 {got}")
        return problems
    if not expected_intake:
        return problems

    expected_ask = {field for field in row["ask"].split(";") if field}
    got_ask = set(missing_fields(result))
    if expected_ask != got_ask:
        problems.append(f"되물을 항목: 정답 {sorted(expected_ask)}, 결과 {sorted(got_ask)}")

    for field in ("equipment", "status"):
        if row[field] and result[field] != row[field]:
            problems.append(f"{field}: 정답 {row[field]}, 결과 {result[field]}")
    return problems


def main():
    with DATA.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    passed = 0
    for row in rows:
        result = extract(row["utterance"])
        problems = check(row, result)
        if problems:
            print(f"[실패] {row['id']} {row['utterance']}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            passed += 1
            print(f"[통과] {row['id']}")

    print(f"\n{passed}/{len(rows)} 통과")


if __name__ == "__main__":
    main()
