# TVING 자동 로그인 및 profileNo 추출 자동화

TVING 웹페이지에 로그인한 뒤, 백엔드 API 응답에서 `profileNo`를 추출하는 자동화 프로젝트입니다.

> 💡 **핵심 요구사항 구현 위치 (TL;DR)**
> - **profileNo API 추출 핵심 로직**: [`pages/my_page.py`](pages/my_page.py) (`extract_profile_from_api()`)
> - **로그인 및 다중 프로필 선택 제어**: [`pages/login_page.py`](pages/login_page.py) (`perform_login()`, `handle_profile_selection()`)
> - **E2E 실행 진입점**: [`main.py`](main.py) (POM 기반 전체 플로우) / [`quick.py`](quick.py) (단일 및 배치 비교 검증)

---

## 1. 주요 구현 포인트

### 1) 목적에 맞춘 2가지 실행 모드 제공
- **과제 기본 모드 (`main.py`)**: 실제 사용자 탐색 플로우를 준수하여 메인 ➡️ 로그인 ➡️ 프로필 메뉴 ➡️ 마이페이지 UI로 이동한 뒤 데이터를 추출합니다.
- **빠른 검증 및 배치 모드 (`quick.py`)**: 마이페이지 이동 없이 로그인 직후 API 응답을 즉시 가로채어 소요 시간을 단축합니다. 특히 **`accounts.json` 파일에 등록된 다수의 계정을 순차적으로 로그인하여 실제 발급된 `profileNo`가 DB 기준 기대값과 일치하는지 일괄 비교(PASS/FAIL)하는 배치 검증 기능(`--file`)**을 지원하여 실무 QA 테스트 환경에서도 바로 활용할 수 있도록 설계했습니다.

### 2) OTT 다중 프로필 계정 완벽 지원 (자동 선택 & 지정 선택)
- 1계정 다중 프로필(가족 공유, 키즈 분리 등)을 지원하는 OTT 서비스 특성을 반영하여, 로그인 후 **"프로필을 선택하세요" 화면이 나타나면 자동으로 프로필을 선택**하고 플로우를 이어갑니다.
  - **기본 동작**: 프로필을 별도로 지정하지 않으면 첫 번째(기본) 프로필 카드를 자동 선택하여 멈춤 없이 통과합니다.
  - **특정 프로필 지정**: CLI 인자(`--profile "프로필명"`) 또는 배치 파일(`"target_profile": "키즈"`)로 원하는 프로필을 명시하여 테스트할 수 있습니다.
  - **단일 프로필 계정**: 선택 화면이 나타나지 않으므로 딜레이 없이 즉시 다음 단계로 진행합니다.
  - **전체 프로필 정보 수집**: 활성 프로필뿐만 아니라 해당 계정에 등록된 **전체 프로필 목록(`all_profiles`)**까지 함께 수집하여 리포트에 출력합니다.

### 3) 로그인 수단 다변화 지원 (티빙 ID & CJ ONE 계정)
- 티빙 전용 계정(`tving`)뿐만 아니라, 많은 사용자가 이용하는 **CJ ONE 통합 아이디(`cjone`)** 로그인 방식을 모두 지원합니다.
- CLI 인자(`--login-type cjone`) 또는 배치 파일(`"login_type": "cjone"`)을 통해 유연하게 로그인 수단을 전환할 수 있습니다.

### 4) 안정적인 셀렉터 (`data-testid`) 활용
- 화면 변경이나 다국어 처리 시 깨지기 쉬운 텍스트나 클래스명 대신, 개발/QA용으로 심어져 있는 고유 속성(`data-testid`)을 우선 사용했습니다.
  - 메인 로그인 버튼: `[data-testid='nav-login-button']`
  - 프로필 메뉴 트리거: `[data-testid='nav-profile-menu-trigger']`
  - 마이페이지 링크: `[data-testid='nav-profile-menu-my']`

### 5) 실제 사용자 탐색 플로우 반영
- 로그인 후 URL(`tving.com/my`)로 바로 건너뛰지 않고, 우측 상단 프로필 아이콘을 눌러 나타나는 'MY' 메뉴를 직접 클릭해 이동하도록 구성했습니다. (UI 탐색 실패 시 URL 직접 이동으로 자동 대체)

### 6) API 응답(Network Interception)에서 데이터 추출
- 마이페이지 화면의 DOM 텍스트를 파싱하는 방식 대신, 브라우저가 주고받는 네트워크 패킷 중 유저 정보 API(`api.tving.com/v2/user/info`) 응답을 직접 가로채서 `profileNo`를 안전하게 가져옵니다.

### 7) 간헐적 오류 팝업 자동 처리
- 로그인 시 종종 발생하는 "일시적인 서비스 오류" 팝업 감지 시, 자동으로 확인 버튼을 누르고 잠시 대기 후 재시도하도록 예외 처리를 추가했습니다.

---

## 2. 파일 구조 (Page Object Model)

유지보수성과 가독성을 위해 UI 제어 로직과 테스트 시나리오를 분리하는 Page Object Model(POM) 패턴을 적용했습니다.

```text
tving_auto/
├── main.py                  # 과제 기본 실행 스크립트 (POM 기반 E2E 플로우)
├── quick.py                 # 단일/배치 빠른 추출 스크립트
├── config.py                # CLI 인자 및 터미널 입력 처리
├── models.py                # 추출 결과 데이터 모델 (ProfileInfo, ExtractionResult)
├── pages/                   # Page Object Model (페이지별 화면 제어)
│   ├── base_page.py         # 브라우저 공통 제어 및 유틸리티
│   ├── login_page.py        # 로그인 화면 제어 및 다중 프로필 선택 처리
│   └── my_page.py           # 마이페이지 진입 및 API 가로채기
├── accounts.example.json    # 배치 검증용 샘플 데이터
└── requirements.txt         # 의존성 패키지 (Playwright)
```

---

## 3. 실행 방법

### 1) 패키지 설치
```bash
# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Mac/Linux

# 필수 패키지 및 브라우저 설치
pip install -r requirements.txt
playwright install chromium
```

### 2) 실행 모드별 명령어

| 구분 | `main.py` (과제 기본) | `quick.py` (빠른 검증) |
| :--- | :--- | :--- |
| **용도** | 전체 E2E UI 탐색 및 검증 | 단일/다중 계정 빠른 profileNo 추출 |
| **마이페이지 진입** | UI 메뉴를 거쳐 직접 이동 | 로그인 직후 API만 포착하여 즉시 종료 |
| **로그인 유형** | 티빙 ID / CJ ONE 계정 (`--login-type`) | 티빙 ID / CJ ONE 계정 (`--login-type`) |
| **다중 프로필 처리** | 첫 번째 프로필 자동 선택 (또는 `--profile` 지정) | 첫 번째 프로필 자동 선택 (또는 `--profile` 지정) |
| **소요 시간** | 약 10~20초 | 약 10초 |

#### [기본] `main.py` 실행
```bash
# 1. 기본 실행 (티빙 아이디 대화형 입력)
python main.py

# 2. 티빙 아이디 CLI 실행
python main.py -u "아이디" -p "비밀번호"

# 3. CJ ONE 계정 로그인 실행
python main.py -u "아이디" -p "비밀번호" --login-type cjone

# 4. 다중 프로필 계정에서 특정 프로필 지정 선택
python main.py -u "아이디" -p "비밀번호" --profile "딴딴"

# 5. 브라우저 화면을 보면서 실행
python main.py -u "아이디" -p "비밀번호" --no-headless

# 6. 결과를 JSON 파일로 저장
python main.py -u "아이디" -p "비밀번호" -o result.json
```

#### [선택] `quick.py` 실행 (빠른 추출 및 배치 검증)
```bash
# 단일 계정 빠른 추출 (티빙 ID)
python quick.py -u "아이디" -p "비밀번호"

# CJ ONE 계정 빠른 추출
python quick.py -u "아이디" -p "비밀번호" --login-type cjone

# 특정 프로필 지정 추출
python quick.py -u "아이디" -p "비밀번호" --login-type cjone --profile "키즈"

# 여러 계정 일괄 비교 검증 (배치 모드)
python quick.py --file accounts.json
```

---

## 4. 배치 검증 모드 (`quick.py --file`)

사내 테스트 계정 목록(`accounts.json`)을 읽어 순차적으로 로그인하고, 실제 발급된 `profileNo`가 DB 기준 기대값(`expected_profile_no`)과 일치하는지 비교하여 PASS/FAIL 결과를 출력합니다.

### 1) 주요 활용 시나리오
* **정기 헬스체크 배치**: 매일 새벽 사내 테스트 계정 전수 검증 ➡️ 프로필 매핑 오류나 계정 만료 상태를 사전에 감지
* **배포 후 스모크 테스트**: 신규 배포 후 핵심 계정들의 로그인 및 profileNo 조회가 여전히 정상 동작하는지 신속 검증

### 2) 설정 파일 형식 (`accounts.json`)
> **검증 원칙**: `expected_profile_no`는 반드시 DB에서 직접 확인한 기준값을 기입해야 올바른 테스트(Test Oracle)가 성립합니다.  
> 실제 계정 정보가 담긴 `accounts.json`은 보안을 위해 `.gitignore`에 등록되어 있습니다.

```json
[
  {
    "id": "test_tving_01",
    "password": "password1234",
    "login_type": "tving",
    "target_profile": null,
    "expected_profile_no": "511000001",
    "desc": "티빙 아이디 단일 프로필 계정"
  },
  {
    "id": "test_cjone_01",
    "password": "password1234",
    "login_type": "cjone",
    "target_profile": "키즈",
    "expected_profile_no": "505000002",
    "desc": "CJ ONE 다중 프로필 계정 - 특정 프로필('키즈') 지정"
  }
]
```

---

## 5. 실행 결과 예시

### `main.py` 실행 결과 (CJ ONE 다중 프로필 계정 예시)
```text
22:05:38 [INFO] 메인 페이지의 로그인 버튼 클릭 (Selector: [data-testid='nav-login-button'])
22:05:41 [INFO] 'CJ ONE으로 시작하기' 옵션 선택 (Selector: a[href*='/account/login/cj-one'])
22:05:41 [INFO] 로그인 시도 - 사용자 ID: test_cjone_user
22:05:44 [INFO] 로그인 인증 성공!
22:05:45 [INFO] 다중 프로필 선택 화면 감지. 프로필 선택 진행 (지정 프로필: 키즈)
22:05:45 [INFO] 프로필 카드 자동 선택 완료: '키즈'
22:05:46 [INFO] Network Intercept: TVING 유저 정보 API(/v2/user/info) 응답 포착 완료
22:05:47 [INFO] 마이페이지 진입 플로우 시작 (UI 프로필 메뉴 경유)...
22:05:47 [INFO] 프로필 아이콘 클릭/호버: [data-testid='nav-profile-menu-trigger']
22:05:48 [INFO] 드롭다운 메뉴의 'MY' 클릭: [data-testid='nav-profile-menu-my']
22:05:49 [INFO] 마이페이지 UI 진입 성공: https://www.tving.com/my
22:05:49 [INFO] 백엔드 API(/v2/user/info) 응답 포착 완료

============================================================
          TVING profileNo 추출 결과
============================================================
 [★] profileNo       : 505000002
 [-] 프로필 명       : 키즈
 [-] 사용자 ID       : test_cjone_user
 [-] 사용자 명       : 홍길동
 [-] 회원 번호(userNo): 505000002
 [-] 데이터 출처     : 백엔드 API (/v2/user/info)
 [-] 총 소요 시간    : 12.05초
 [-] 보유 프로필 목록 (2개):
       1. 기본프로필 (profileNo: 505000001)
       2. 키즈 (profileNo: 505000002)
============================================================
```

### `quick.py --file` 배치 실행 결과
```text
======================================================================
  TVING profileNo 배치 검증 시작 (총 3개 계정)
======================================================================

[1/3] [TVING] test_tving_01 (티빙 아이디 단일 프로필 계정)
  상태        : PASS
  기대값      : 511000001
  실제값      : 511000001 (기본프로필)
  소요 시간   : 10.5s

[2/3] [CJONE] test_cjone_01 (CJ ONE 다중 프로필 계정, 대상 프로필: '키즈')
  상태        : PASS
  기대값      : 505000002
  실제값      : 505000002 (키즈)
  보유 프로필 : 2개 [기본프로필(505000001), 키즈(505000002)]
  소요 시간   : 10.4s

[3/3] [CJONE] test_cjone_02 (CJ ONE 다중 프로필 계정)
  상태        : FAIL
  기대값      : 505000003
  실제값      : 505000002 (키즈)
  불일치 감지 : expected=505000003  /  actual=505000002
  소요 시간   : 10.4s

======================================================================
  결과: 3건 중  PASS 2  /  FAIL 1  /  ERROR 0
======================================================================
```

---

## 6. 추가 분석 (네트워크 패킷 분석)

과제를 진행하며 실제 네트워크 요청을 분석해본 결과, 다음과 같은 인증 구조를 확인했습니다:

1. **`profileNo`의 용도**:
   - 웹 화면에서 시청 내역이나 찜 목록 등을 조회할 때, URL 파라미터로 `profileNo`를 직접 보내지 않습니다.
   - `profileNo`는 주로 계정별 프로필 매핑 상태를 검증하거나 유저를 식별하는 Primary Key 역할을 합니다.
2. **실제 API 통신 (`profileToken`)**:
   - 실제 후속 API 호출 시에는 로그인 응답에 함께 포함된 `profileToken`을 `Authorization: Bearer {token}` 형태로 헤더에 담아 통신합니다.
   - 본 프로젝트의 `ProfileInfo` 모델에는 향후 API 테스트 연계를 고려해 `profile_token` 값도 함께 수집할 수 있도록 준비해 두었습니다.
