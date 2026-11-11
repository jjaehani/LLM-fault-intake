import json
import os

from openai import OpenAI

FIELDS = ["equipment", "symptom", "onset", "status"]
STATUS_VALUES = ["완전히 멈춤", "느리지만 작동", "정상 작동"]

SYSTEM_PROMPT = """너는 산업장비 고장 접수 챗봇의 정보 추출기다.
접수자의 메시지에서 아래 항목을 뽑는다.
- equipment: 장비 종류 (예: 프레스, 컨베이어)
- symptom: 고장 증상
- onset: 발생 시점 (예: 오늘, 어제, 일주일 전)
- status: 작동 상태. 완전히 멈춤, 느리지만 작동, 정상 작동 중 하나

규칙:
- 메시지에 없는 정보는 추측하지 말고 null로 둔다.
- '지금', '아까'는 오늘로 본다.
- 급하다는 표현만으로 status를 정하지 않는다.
- 고장 접수와 관계없는 메시지면 is_intake를 false로 하고 나머지는 null로 둔다.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "is_intake": {"type": "boolean"},
        "equipment": {"type": ["string", "null"]},
        "symptom": {"type": ["string", "null"]},
        "onset": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"], "enum": STATUS_VALUES + [None]},
    },
    "required": ["is_intake", "equipment", "symptom", "onset", "status"],
    "additionalProperties": False,
}


def extract(message, client=None):
    """접수자 메시지 하나에서 접수 항목을 뽑아 dict로 돌려준다."""
    client = client or OpenAI()
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-5.4-nano"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "intake", "strict": True, "schema": SCHEMA},
        },
    )
    return json.loads(response.choices[0].message.content)


def missing_fields(result):
    """비어 있어서 되물어야 하는 항목 이름 목록."""
    return [field for field in FIELDS if not result.get(field)]
