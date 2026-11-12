# llm-fault-intake

카카오톡 챗봇으로 산업용 전자 장비(HMI, 인버터, 서보드라이브, PLC, 산업용 PC, 파워서플라이)의 고장을 접수하는 LLM 프로젝트입니다. 현재 진행 중입니다.

## 하는 일

접수자가 고장 증상을 평소 말투로 보내면 LLM이 장비, 증상, 증상 분류 코드, 발생 시점, 작업 상태를 뽑고, 빠진 항목은 되묻습니다. LLM이 정리한 내용은 초안이고 최종 확정은 담당자가 합니다.

## 현재 결과

| 데이터 | 문장 수 | 통과 |
|---|---|---|
| 조정용 (`data/dev.csv`) | 20 | 19 |
| 시험용 (`data/holdout.csv`) | 12 | 11 |

모델은 `gemini-3.5-flash-lite`입니다. 실패 사례와 프롬프트를 고친 과정은 [docs/evaluation.md](docs/evaluation.md)에 있습니다. 가상 데이터이고 문장 수가 적어서, 이 숫자는 실제 접수 성능이 아닙니다.

## 문서

- [요구사항 정의서](docs/requirements.md)
- [대화 흐름](docs/conversation-flow.md)
- [화면 설계](docs/screen-design.md)
- [데이터와 증상 분류표](data/README.md)

## 데이터

실제 업체 데이터는 쓰지 않았습니다. 장비 목록, 증상 분류표, 문장은 모두 직접 만들었습니다.

## 실행

Gemini API 키(무료 등급)를 `GEMINI_API_KEY` 환경변수로 설정한 뒤 실행합니다.

```
pip install -r requirements.txt
python scripts/evaluate.py                    # 조정용
python scripts/evaluate.py data/holdout.csv   # 시험용
```

## 진행 상황

- [x] 요구사항 정의, 대화 흐름, 화면 설계
- [x] 가상 증상 데이터와 증상 분류표
- [x] 항목 추출과 채점
- [ ] 되묻기 대화 흐름 구현
- [ ] 카카오톡 챗봇 연결
