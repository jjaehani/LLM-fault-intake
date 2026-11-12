"""대화 흐름 시험. LLM 대신 정해진 답을 돌려주는 가짜 함수를 써서 API 키 없이 돌아간다.

실행: python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dialog import ERROR_REPLY, OFF_TOPIC_REPLY, IntakeDialog  # noqa: E402

EMPTY = {"is_intake": True, "equipment": "", "symptom": "", "symptom_code": "", "onset": "", "status": ""}


def fake(answers):
    """메시지에 들어 있는 글자로 미리 정한 답을 고른다."""

    def extractor(message):
        for key, value in answers.items():
            if key in message:
                if value == "fail":
                    raise RuntimeError("503")
                return {**EMPTY, **value}
        return dict(EMPTY)

    return extractor


class IntakeDialogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "intakes.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        with self.save_path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_빠진_항목을_차례로_묻고_접수한다(self):
        dialog = IntakeDialog(
            fake({"OC 알람": {"equipment": "인버터", "symptom": "과전류 알람", "symptom_code": "INV-ALM-01"}}),
            self.save_path,
        )
        self.assertIn("언제부터", dialog.handle("인버터 OC 알람 떴어요"))
        self.assertIn("어떤 상태", dialog.handle("오늘"))
        reply = dialog.handle("1")
        self.assertIn("INV-ALM-01", reply)
        self.assertIn("긴급도: 높음", reply)
        self.assertIn("F-0001", dialog.handle("1"))

        record = self.records()[0]
        self.assertEqual(record["state"], "접수됨")
        self.assertEqual(record["intake"]["status"], "완전히 멈춤")
        self.assertEqual(record["messages"][0], "인버터 OC 알람 떴어요")

    def test_장비를_다른_이름으로_답해도_목록_이름으로_맞춘다(self):
        dialog = IntakeDialog(
            fake({"모터": {"symptom": "모터 안 돎"}, "서보드라이브 모터": {"equipment": "서보드라이브", "symptom": "모터 안 돎"}}),
            self.save_path,
        )
        self.assertIn("어떤 장비", dialog.handle("모터가 안 돌아요"))
        dialog.handle("서보앰프요")
        self.assertEqual(dialog.intake["equipment"], "서보드라이브")

    def test_범위_밖_질문에는_접수_안내로_답한다(self):
        dialog = IntakeDialog(fake({"영업": {"is_intake": False}}), self.save_path)
        self.assertEqual(dialog.handle("몇 시까지 영업해요?"), OFF_TOPIC_REPLY)

    def test_호출이_실패해도_대화를_파일에_남긴다(self):
        dialog = IntakeDialog(fake({"PLC": "fail"}), self.save_path)
        self.assertEqual(dialog.handle("PLC 출력이 안 나가요"), ERROR_REPLY)
        record = self.records()[0]
        self.assertEqual(record["state"], "호출 실패")
        self.assertEqual(record["messages"], ["PLC 출력이 안 나가요"])

    def test_확인_단계에서_항목을_고칠_수_있다(self):
        dialog = IntakeDialog(
            fake({"HMI 화면": {"equipment": "HMI", "symptom": "화면 안 나옴", "symptom_code": "HMI-SCR-01", "onset": "오늘", "status": "완전히 멈춤"}}),
            self.save_path,
        )
        self.assertIn("맞나요", dialog.handle("HMI 화면이 안 나와요 오늘부터 라인 섰어요"))
        self.assertIn("어떤 항목", dialog.handle("2"))
        self.assertIn("언제부터", dialog.handle("3"))
        self.assertIn("발생 시점: 어제", dialog.handle("어제"))

    def test_작업_상태는_번호로만_받는다(self):
        dialog = IntakeDialog(
            fake({"파워": {"equipment": "파워서플라이", "symptom": "출력 안 나옴", "onset": "오늘"}}),
            self.save_path,
        )
        dialog.handle("파워 출력이 안 나와요 오늘부터")
        self.assertIn("1, 2, 3 중에서", dialog.handle("모르겠어요"))

    def test_답에_다른_장비가_섞이면_확인하고_고친다(self):
        dialog = IntakeDialog(
            fake({
                "서보드라이브 모터": {"equipment": "서보드라이브", "symptom": "모터가 안 돈다"},
                "서보 어제": {"equipment": "서보드라이브", "onset": "어제"},
                "모터": {"equipment": "인버터", "symptom": "모터가 안 돈다", "symptom_code": "INV-OUT-01"},
            }),
            self.save_path,
        )
        self.assertIn("언제부터", dialog.handle("모터가 안 돌아요"))
        self.assertIn("앞에서는 인버터", dialog.handle("서보 어제요"))
        self.assertIn("어떤 상태", dialog.handle("1"))
        self.assertEqual(dialog.intake["equipment"], "서보드라이브")
        self.assertEqual(dialog.intake["onset"], "어제")
        self.assertEqual(dialog.intake["symptom_code"], "")  # 인버터 코드는 버린다

    def test_다른_고장을_말하면_새로_접수하고_앞의_내용은_남긴다(self):
        dialog = IntakeDialog(
            fake({
                "HMI 화면": {"equipment": "HMI", "symptom": "화면이 안 나온다", "symptom_code": "HMI-SCR-01", "onset": "오늘", "status": "완전히 멈춤"},
                "모터": {"equipment": "인버터", "symptom": "모터가 안 돈다", "symptom_code": "INV-OUT-01"},
            }),
            self.save_path,
        )
        dialog.handle("모터가 안 돌아요")
        self.assertIn("방금 HMI", dialog.handle("HMI 화면이 안 나와요 오늘 아침부터 라인 섰어요"))
        reply = dialog.handle("2")
        self.assertIn("장비: HMI", reply)
        self.assertIn("발생 시점: 오늘", reply)
        record = self.records()[0]
        self.assertEqual(record["state"], "작성 중 중단")
        self.assertEqual(record["intake"]["equipment"], "인버터")


if __name__ == "__main__":
    unittest.main()
