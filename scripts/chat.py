"""터미널에서 고장 접수 챗봇과 대화한다. 끝내려면 q를 입력한다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.dialog import IntakeDialog  # noqa: E402

SAVE_PATH = ROOT / "outputs" / "intakes.jsonl"


def show(reply):
    print("[챗봇] " + reply.replace("\n", "\n       "))


def main():
    dialog = IntakeDialog(save_path=SAVE_PATH)
    print("끝내려면 q를 입력하세요. 접수 기록은 outputs/intakes.jsonl에 저장됩니다.\n")
    show("안녕하세요. 장비 고장 접수를 도와드려요.\n어떤 장비가 어떻게 고장 났는지 말씀해 주세요.")
    while True:
        try:
            text = input("[나] ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip().lower() == "q":
            break
        show(dialog.handle(text))


if __name__ == "__main__":
    main()
