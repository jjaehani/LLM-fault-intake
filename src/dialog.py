"""되묻기 대화 흐름.

카카오톡과 연결하기 전에 터미널에서 시험한다. 접수자 메시지를 받아 챗봇 답을 돌려준다.
LLM은 처음 메시지와 증상 답변에서만 부르고, 질문 문구와 선택지는 고정해 둔다.
"""

import json
from datetime import datetime
from pathlib import Path

from src.extract import EQUIPMENT, FIELDS, STATUS_VALUES, TAXONOMY, extract

QUESTIONS = {
    "equipment": "어떤 장비인가요? (예: HMI, 인버터, 서보, PLC, 산업용 PC, 파워)",
    "symptom": "어떤 증상인지 조금 더 자세히 알려 주세요.",
    "onset": "언제부터 그랬나요? (예: 오늘, 어제, 일주일 전)",
    "status": "지금 라인이나 작업은 어떤 상태인가요?\n  1. 완전히 멈춤\n  2. 느리지만 작동\n  3. 정상 작동",
}
LABELS = {"equipment": "장비", "symptom": "증상", "onset": "발생 시점", "status": "작업 상태"}
URGENCY = {"완전히 멈춤": "높음", "느리지만 작동": "중간", "정상 작동": "낮음"}
CODE_DETAIL = {row["code"]: row["detail"] for row in TAXONOMY}

OFF_TOPIC_REPLY = "저는 장비 고장 접수만 도와드릴 수 있어요. 고장 난 장비와 증상을 말씀해 주세요."
ERROR_REPLY = (
    "지금 접수 정리가 잠시 안 되고 있어요. 입력하신 내용은 저장해 두었어요.\n"
    "잠시 뒤 다시 보내 주시거나, 급하시면 담당자에게 직접 접수해 주세요."
)


def match_equipment(text):
    """답변에서 장비 목록의 이름이나 다른 이름을 찾는다. 없으면 빈 문자열."""
    key = text.replace(" ", "").lower()
    for row in EQUIPMENT:
        names = [row["name"]] + [alias for alias in row["aliases"].split(";") if alias]
        if any(name.replace(" ", "").lower() in key for name in names):
            return row["name"]
    return ""


class IntakeDialog:
    def __init__(self, extractor=extract, save_path=None):
        self.extractor = extractor
        self.save_path = Path(save_path) if save_path else None
        self.reset()

    def reset(self):
        self.intake = {field: "" for field in FIELDS + ["symptom_code"]}
        self.messages = []
        self.waiting_for = None  # 지금 답을 기다리는 항목
        self.stage = "collect"  # collect, confirm, choose_fix

    def handle(self, text):
        text = text.strip()
        if not text:
            return "메시지를 입력해 주세요."
        self.messages.append(text)

        if self.stage == "confirm":
            return self._handle_confirm(text)
        if self.stage == "choose_fix":
            return self._handle_choose_fix(text)
        if self.waiting_for:
            return self._handle_answer(text)
        return self._handle_first(text)

    def _call(self, text):
        """LLM 호출이 실패하면 None을 돌려주고, 지금까지의 대화를 파일에 남긴다."""
        try:
            return self.extractor(text)
        except Exception:
            self._save(state="호출 실패")
            return None

    def _handle_first(self, text):
        result = self._call(text)
        if result is None:
            self.messages.pop()  # 다시 보내면 처음 메시지로 다시 처리한다
            return ERROR_REPLY
        if not result["is_intake"]:
            return OFF_TOPIC_REPLY
        for field in FIELDS + ["symptom_code"]:
            self.intake[field] = result[field]
        return self._next()

    def _handle_answer(self, text):
        field = self.waiting_for

        if field == "status":
            choice = {"1": STATUS_VALUES[0], "2": STATUS_VALUES[1], "3": STATUS_VALUES[2]}.get(text[:1])
            choice = choice or (text if text in STATUS_VALUES else "")
            if not choice:
                return "1, 2, 3 중에서 골라 주세요.\n" + QUESTIONS["status"]
            self.intake["status"] = choice

        elif field == "onset":
            self.intake["onset"] = text

        elif field == "equipment":
            self.intake["equipment"] = match_equipment(text) or text
            self.intake["symptom_code"] = ""
            if self.intake["symptom"]:
                result = self._call(f"{self.intake['equipment']} {self.intake['symptom']}")
                if result and result["equipment"] == self.intake["equipment"]:
                    self.intake["symptom_code"] = result["symptom_code"]

        elif field == "symptom":
            result = self._call(f"{self.intake['equipment']} {text}".strip())
            if result is None:
                return ERROR_REPLY
            # 모델이 증상을 못 뽑으면 접수자의 말을 그대로 두고 담당자가 확인한다.
            self.intake["symptom"] = result["symptom"] or text
            self.intake["symptom_code"] = ""
            if result["equipment"] == self.intake["equipment"]:
                self.intake["symptom_code"] = result["symptom_code"]
            for other in ("onset", "status"):
                if result[other] and not self.intake[other]:
                    self.intake[other] = result[other]

        self.waiting_for = None
        return self._next()

    def _next(self):
        for field in FIELDS:
            if not self.intake[field]:
                self.waiting_for = field
                return QUESTIONS[field]
        self.stage = "confirm"
        return self._summary() + "\n\n이렇게 접수할게요. 맞나요?\n  1. 맞아요\n  2. 고칠게요"

    def _summary(self):
        code = self.intake["symptom_code"]
        code_text = f"{code} ({CODE_DETAIL[code]})" if code else "담당자 확인 필요"
        lines = [f"{LABELS[field]}: {self.intake[field]}" for field in FIELDS]
        lines.insert(2, f"증상 분류: {code_text}")
        lines.append(f"긴급도: {URGENCY[self.intake['status']]}")
        return "\n".join(lines)

    def _handle_confirm(self, text):
        if text.startswith("1") or text.startswith("맞"):
            intake_id = self._save(state="접수됨")
            self.reset()
            return f"접수됐어요. 접수 번호는 {intake_id}이에요.\n담당자가 내용을 확인한 뒤 연락드릴게요."
        if text.startswith("2") or text.startswith("고칠"):
            self.stage = "choose_fix"
            options = "\n".join(f"  {i}. {LABELS[field]}" for i, field in enumerate(FIELDS, 1))
            return "어떤 항목을 고칠까요?\n" + options
        return "1 또는 2로 답해 주세요.\n  1. 맞아요\n  2. 고칠게요"

    def _handle_choose_fix(self, text):
        index = text[:1]
        if index not in {"1", "2", "3", "4"}:
            return "1부터 4 중에서 골라 주세요."
        field = FIELDS[int(index) - 1]
        self.stage = "collect"
        self.waiting_for = field
        return QUESTIONS[field]

    def _save(self, state):
        """접수 기록을 한 줄씩 덧붙인다. 담당자가 원문과 비교할 수 있게 메시지도 남긴다."""
        if not self.save_path:
            return "F-0000"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if self.save_path.exists():
            with self.save_path.open(encoding="utf-8") as f:
                count = sum(1 for _ in f)
        intake_id = f"F-{count + 1:04d}"
        record = {
            "id": intake_id,
            "state": state,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "intake": self.intake,
            "messages": self.messages,
        }
        with self.save_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return intake_id
