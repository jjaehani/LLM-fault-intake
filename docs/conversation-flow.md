# 대화 흐름도

접수자가 카카오톡 챗봇에 증상을 말한 뒤 담당자가 확정하기까지의 흐름이다.
노드 아래의 ID는 [요구사항 정의서](requirements.md)의 요구사항과 같다.

## 접수 흐름

```mermaid
flowchart TD
    A["접수자가 카카오톡에 증상 입력<br>FIT-001"] --> B{"접수와 관련된 내용인가<br>FIT-008"}
    B -->|아니오| C["접수 안내로 되돌리는 답변"]
    C --> A
    B -->|예| D["LLM이 접수 항목 추출<br>FIT-002"]
    D -->|호출 실패| E["입력 내용 보존<br>담당자 직접 접수 안내<br>FIT-NF4"]
    D --> F{"빠진 항목이 있는가<br>FIT-003"}
    F -->|예| G["접수자에게 한 가지씩 되묻기"]
    G --> D
    F -->|아니오| H["정리된 내용을 접수자에게 보여 줌<br>FIT-004"]
    H --> I{"접수자가 맞다고 확인했는가"}
    I -->|아니오| J["틀린 항목을 다시 입력받음"]
    J --> D
    I -->|예| K["담당자에게 전달<br>FIT-006"]
    K --> L["담당자가 내용을 고치고 최종 확정<br>FIT-007"]
    L --> M["접수 완료"]
```

사진 첨부(FIT-005)는 접수 중에 보낼 수 있고, 해당 접수에 연결해 저장한다.

## 접수 상태

접수자가 조회하는 상태(FIT-009)는 세 가지다.

```mermaid
stateDiagram-v2
    state "접수됨" as received
    state "담당자 확인 중" as reviewing
    state "확정" as confirmed
    [*] --> received: 접수자가 내용 확인
    received --> reviewing: 담당자에게 전달
    reviewing --> confirmed: 담당자가 확정
    confirmed --> [*]
```
