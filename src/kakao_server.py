"""카카오 i 오픈빌더 스킬 서버.

오픈빌더가 접수자 메시지를 POST /skill 로 보내면, 대화 흐름(src/dialog.py)에 넘기고
카카오 응답 형식으로 돌려준다. 접수자별 대화 상태는 메모리에 둔다.

실행: uvicorn src.kakao_server:app --host 0.0.0.0 --port 8000
"""

import re
import time
from pathlib import Path

from fastapi import FastAPI, Request

from src.dialog import IntakeDialog
from src.extract import extract, make_client

ROOT = Path(__file__).resolve().parent.parent
SAVE_PATH = ROOT / "outputs" / "intakes.jsonl"

# 카카오는 스킬 서버가 5초 안에 답하지 않으면 실패로 처리한다.
# LLM 호출을 4초에서 끊고, 끊기면 대화 흐름의 오류 안내(FIT-NF4)로 넘어간다.
LLM_TIMEOUT_SECONDS = 4

OPTION_LINE = re.compile(r"^\s*([1-9])\.\s*(.+)$")
MAX_LABEL = 14  # 바로가기 버튼 글자 수 제한에 맞춘다

app = FastAPI()
_client = None
sessions = {}


def llm_extract(message):
    global _client
    if _client is None:
        _client = make_client(timeout=LLM_TIMEOUT_SECONDS, max_retries=0)
    started = time.monotonic()
    try:
        return extract(message, client=_client)
    finally:
        print(f"LLM 호출 {time.monotonic() - started:.1f}초")


def make_dialog():
    return IntakeDialog(extractor=llm_extract, save_path=SAVE_PATH)


def to_kakao(reply):
    """대화 흐름의 답을 카카오 응답 형식으로 바꾼다. 번호 선택지는 바로가기 버튼으로 만든다."""
    text_lines, buttons = [], []
    for line in reply.split("\n"):
        match = OPTION_LINE.match(line)
        if match:
            number, label = match.groups()
            buttons.append({"label": label[:MAX_LABEL], "action": "message", "messageText": number})
        text_lines.append(line.strip())

    template = {"outputs": [{"simpleText": {"text": "\n".join(text_lines)}}]}
    if buttons:
        template["quickReplies"] = buttons
    return {"version": "2.0", "template": template}


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/skill")
async def skill(request: Request):
    body = await request.json()
    user_request = body.get("userRequest", {})
    user_id = user_request.get("user", {}).get("id", "anonymous")
    utterance = user_request.get("utterance", "")

    dialog = sessions.setdefault(user_id, make_dialog())
    return to_kakao(dialog.handle(utterance))
