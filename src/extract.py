import json
import os

from openai import OpenAI

FIELDS = ["equipment", "symptom", "onset", "status"]
STATUS_VALUES = ["완전히 멈춤", "느리지만 작동", "정상 작동"]

# 실제 서비스라면 업체의 장비 목록에서 가져온다.
EQUIPMENT = ["프레스", "컨베이어", "공기압축기", "CNC 선반", "사출기", "용접기", "지게차"]

SYSTEM_PROMPT = f"""너는 산업장비 고장 접수 챗봇의 정보 추출기다.
접수자의 메시지에서 아래 항목을 뽑아 JSON으로 답한다.
- is_intake: 장비 고장 접수와 관련된 메시지면 true
- equipment: 장비 종류
- symptom: 고장 증상
- onset: 발생 시점 (예: 오늘, 어제, 일주일 전)
- status: 작동 상태. 완전히 멈춤, 느리지만 작동, 정상 작동 중 하나

장비 이름은 이 목록의 이름으로 맞춘다: {", ".join(EQUIPMENT)}
목록에 없는 장비는 접수자가 말한 그대로 쓴다.

규칙:
- 메시지에 없는 정보는 추측하지 말고 빈 문자열("")로 둔다.
- '지금', '아까'는 오늘로 본다.
- status는 접수자가 장비가 돌아가는지를 직접 말한 경우에만 채운다. 증상을 보고 짐작하지 않는다.
- '멈췄다'처럼 작동 상태를 말한 표현밖에 없으면 그 표현을 증상에도 적는다.
- '이상하다', '고장났다'처럼 어떤 문제인지 알 수 없는 말은 증상으로 보지 않는다.
- 급하다는 표현만으로 status를 정하지 않는다.
- 장비나 증상이 없어도 고장 접수를 원하는 메시지(예: 급해요, 도와주세요)는 is_intake를 true로 한다.
- 고장 접수와 관계없는 메시지면 is_intake를 false로 하고 나머지는 빈 문자열로 둔다.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "is_intake": {"type": "boolean"},
        "equipment": {"type": "string"},
        "symptom": {"type": "string"},
        "onset": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["is_intake", "equipment", "symptom", "onset", "status"],
}

# 기본값은 무료 등급이 있는 Gemini API의 OpenAI 호환 주소다.
# 다른 서비스로 바꾸려면 LLM_BASE_URL, LLM_API_KEY, LLM_MODEL 환경변수를 설정한다.
BASE_URL = os.environ.get(
    "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")


def make_client():
    # 응답이 30초 안에 없으면 실패로 처리한다. 실패 시 재시도는 1번만 한다.
    return OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=30, max_retries=1)


def clean(result):
    """모델 답을 정해진 형태로 맞춘다. 허용되지 않은 작동 상태는 비운다."""
    cleaned = {"is_intake": bool(result.get("is_intake"))}
    for field in FIELDS:
        value = result.get(field)
        cleaned[field] = value.strip() if isinstance(value, str) else ""
    if cleaned["status"] not in STATUS_VALUES:
        cleaned["status"] = ""
    return cleaned


def extract(message, client=None):
    """접수자 메시지 하나에서 접수 항목을 뽑아 dict로 돌려준다."""
    client = client or make_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "intake", "schema": SCHEMA},
        },
    )
    return clean(json.loads(response.choices[0].message.content))


def missing_fields(result):
    """비어 있어서 되물어야 하는 항목 이름 목록."""
    return [field for field in FIELDS if not result.get(field)]
