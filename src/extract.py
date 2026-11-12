import csv
import json
import os
from pathlib import Path

from openai import OpenAI

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FIELDS = ["equipment", "symptom", "onset", "status"]
STATUS_VALUES = ["완전히 멈춤", "느리지만 작동", "정상 작동"]


def load_csv(name):
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# 실제 서비스라면 업체의 장비 목록과 증상 분류표에서 가져온다.
EQUIPMENT = load_csv("equipment.csv")
TAXONOMY = load_csv("taxonomy.csv")
CODE_TO_EQUIPMENT = {row["code"]: row["equipment"] for row in TAXONOMY}

EQUIPMENT_LINES = "\n".join(
    f"- {row['name']} (다르게 부르는 말: {row['aliases'].replace(';', ', ')})"
    for row in EQUIPMENT
)
TAXONOMY_LINES = "\n".join(
    f"- {row['code']}: {row['equipment']} / {row['group']} / {row['detail']}"
    for row in TAXONOMY
)

SYSTEM_PROMPT = f"""너는 산업용 전자 장비 고장 접수 챗봇의 정보 추출기다.
접수자의 메시지에서 아래 항목을 뽑아 JSON으로 답한다.
- is_intake: 장비 고장 접수와 관련된 메시지면 true
- equipment: 장비 종류
- symptom: 접수자가 말한 고장 증상
- symptom_code: 증상 분류 코드
- onset: 발생 시점 (예: 오늘, 어제, 일주일 전)
- status: 작동 상태. 완전히 멈춤, 느리지만 작동, 정상 작동 중 하나

장비 목록:
{EQUIPMENT_LINES}
장비 이름은 이 목록의 이름으로 맞춘다. 목록에 없는 장비는 접수자가 말한 그대로 쓴다.

증상 분류 목록 (코드: 장비 / 묶음 / 세부 증상):
{TAXONOMY_LINES}

규칙:
- 메시지에 없는 정보는 추측하지 말고 빈 문자열("")로 둔다.
- '지금', '아까'는 오늘로 본다.
- status는 고장 난 부품이 아니라 그 부품이 들어간 라인과 작업이 지금 돌아가는지다. 접수자가 라인, 설비, 생산, 작업이 어떤 상태인지 직접 말한 경우에만 채운다.
  - 완전히 멈춤: 라인이 섰다, 설비가 멈췄다, 작업을 못 한다
  - 느리지만 작동: 작업은 하고 있다, 겨우 돌리고 있다, 생산이 느려졌다
  - 부품의 증상만 말했으면(예: 화면이 안 나온다, 전압이 안 나온다, 모터가 안 돈다, 전원이 안 들어온다) 라인 상태를 짐작하지 말고 비운다.
  - '멈췄다'가 부품을 말하는지 라인을 말하는지 알 수 없으면 비운다.
- '멈췄다'처럼 작동 상태를 말한 표현밖에 없으면 그 표현을 증상에도 적는다.
- '이상하다', '고장났다'처럼 어떤 문제인지 알 수 없는 말은 증상으로 보지 않는다.
- symptom_code는 증상 분류 목록에서 equipment와 같은 장비의 코드 하나만 고른다.
  - 장비를 모르거나, 목록에 맞는 코드가 없거나, 어느 코드인지 판단할 수 없으면 비운다.
  - 알람이 표시됐으면 알람 묶음의 코드를 고른다. 알람 번호의 뜻은 짐작하지 않고, 목록에 이름이 없는 알람은 '종류를 모른다' 코드를 고른다.
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
        "symptom_code": {"type": "string"},
        "onset": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["is_intake", "equipment", "symptom", "symptom_code", "onset", "status"],
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
    """모델 답을 정해진 형태로 맞춘다.

    허용되지 않은 작동 상태, 목록에 없는 코드, 장비와 맞지 않는 코드는 비운다.
    """
    cleaned = {"is_intake": bool(result.get("is_intake"))}
    for field in FIELDS + ["symptom_code"]:
        value = result.get(field)
        cleaned[field] = value.strip() if isinstance(value, str) else ""
    if cleaned["status"] not in STATUS_VALUES:
        cleaned["status"] = ""
    if CODE_TO_EQUIPMENT.get(cleaned["symptom_code"]) != cleaned["equipment"]:
        cleaned["symptom_code"] = ""
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
