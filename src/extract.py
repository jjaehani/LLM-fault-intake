import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.extract import extract, missing_fields  # noqa: E402

DATA = ROOT / "data" / "symptoms.csv"
DELAY_SECONDS = 7
RETRY_WAITS = [10, 30]  # 호출이 실패하면 10초, 30초 쉬고 다시 시도한다


def extract_with_retry(message):
    """서버 과부하(503)나 한도 초과(429)로 실패하면 쉬었다가 다시 시도한다."""
    for wait in RETRY_WAITS:
        try:
            return extract(message)
        except Exception as error:
            print(f"  (호출 실패: {type(error).__name__}, {wait}초 후 다시 시도)")
            time.sleep(wait)
    return extract(message)


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

    passed = failed = errored = 0
    for i, row in enumerate(rows):
        if i > 0:
            time.sleep(DELAY_SECONDS)
        try:
            result = extract_with_retry(row["utterance"])
        except Exception as error:
            errored += 1
            print(f"[오류] {row['id']} 호출 실패로 채점하지 못함 ({type(error).__name__})")
            continue

        problems = check(row, result)
        if problems:
            failed += 1
            print(f"[실패] {row['id']} {row['utterance']}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            passed += 1
            print(f"[통과] {row['id']}")

    print(f"\n통과 {passed}, 실패 {failed}, 호출 오류 {errored} (전체 {len(rows)})")


if __name__ == "__main__":
    main()
