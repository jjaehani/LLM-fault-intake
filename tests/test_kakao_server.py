"""카카오 스킬 서버 시험. LLM 대신 가짜 함수를 쓴다.

실행: python -m unittest discover tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import src.kakao_server as server  # noqa: E402
from src.dialog import IntakeDialog  # noqa: E402


def kakao_body(user_id, utterance):
    return {"userRequest": {"utterance": utterance, "user": {"id": user_id}}}


class KakaoServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        save_path = Path(self.tmp.name) / "intakes.jsonl"

        def fake_extract(message):
            result = {"is_intake": True, "equipment": "", "symptom": "", "symptom_code": "", "onset": "", "status": ""}
            if "PLC" in message:
                result.update(equipment="PLC", symptom="출력이 안 나간다", symptom_code="PLC-IO-02")
            return result

        server.sessions.clear()
        server.make_dialog = lambda: IntakeDialog(extractor=fake_extract, save_path=save_path)
        self.client = TestClient(server.app)

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, user_id, utterance):
        response = self.client.post("/skill", json=kakao_body(user_id, utterance))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_카카오_응답_형식으로_답한다(self):
        body = self.send("u1", "PLC 출력 안 나가요")
        self.assertEqual(body["version"], "2.0")
        self.assertIn("언제부터", body["template"]["outputs"][0]["simpleText"]["text"])

    def test_번호_선택지는_바로가기_버튼이_된다(self):
        self.send("u1", "PLC 출력 안 나가요")
        body = self.send("u1", "어제")
        self.assertNotIn("1. 완전히 멈춤", body["template"]["outputs"][0]["simpleText"]["text"])
        buttons = body["template"]["quickReplies"]
        self.assertEqual([b["messageText"] for b in buttons], ["완전히 멈춤", "느리지만 작동", "정상 작동"])
        body = self.send("u1", "완전히 멈춤")  # 버튼을 누른 것과 같다
        self.assertIn("긴급도: 높음", body["template"]["outputs"][0]["simpleText"]["text"])

    def test_접수자마다_대화를_따로_기억한다(self):
        self.send("u1", "PLC 출력 안 나가요")
        body = self.send("u2", "PLC 출력 안 나가요")
        self.assertIn("언제부터", body["template"]["outputs"][0]["simpleText"]["text"])


if __name__ == "__main__":
    unittest.main()
