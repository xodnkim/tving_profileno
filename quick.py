"""
quick.py - 가장 빠르게 profileNo를 추출하고 기대값과 비교 검증하는 스크립트

[단일 계정 모드]
  python quick.py                                        # 티빙 ID 대화형 입력
  python quick.py -u xodn9900 -p "pw"                   # 티빙 ID CLI 실행
  python quick.py -u cbgg545 -p "pw" --login-type cjone # CJ ONE 계정 로그인
  python quick.py -u cbgg545 -p "pw" --login-type cjone --profile "윤돔"  # 특정 프로필 선택

[배치 검증 모드] --file 옵션
  python quick.py --file accounts.json
  -> JSON 파일의 login_type ("tving" 또는 "cjone")을 자동 인식하여
     순차 검증 후 PASS/FAIL 리포트를 출력합니다.
"""

import sys
import io
import time
import json
import getpass
import argparse
from typing import Optional

# Windows 콘솔 한글/이모지 인코딩 보정
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.sync_api import sync_playwright, Response

TARGET_API = "api.tving.com/v2/user/info"


def get_credentials(args):
    username = args.username
    password = args.password
    if not username:
        prefix = "CJ ONE" if getattr(args, "login_type", "tving") == "cjone" else "TVING"
        print(f"[1/2] {prefix} 아이디: ", end="", flush=True)
        username = input().strip()
    if not password:
        password = getpass.getpass("[2/2] 비밀번호 (입력 안 보임): ").strip()
    return username, password


def extract_profile_no(
    username: str,
    password: str,
    target_profile: Optional[str] = None,
    login_type: str = "tving"
) -> dict:
    """
    핵심 함수: 로그인 후 /v2/user/info API를 가로채 profileNo 및 전체 프로필 정보를 반환.
    - login_type: 'tving' (티빙 ID) 또는 'cjone' (CJ ONE ID)
    - 다중 프로필 선택 화면이 나타나면 target_profile(또는 첫 번째 프로필)을 자동 선택합니다.
    """
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        page = context.new_page()

        def on_response(response: Response):
            try:
                if TARGET_API in response.url:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        captured.append(response.json())
            except Exception:
                pass

        page.on("response", on_response)

        # 메인 페이지 -> 로그인 버튼 -> 로그인 방식 선택
        page.goto("https://www.tving.com/", wait_until="domcontentloaded")
        page.locator("[data-testid='nav-login-button']").first.click()
        page.wait_for_timeout(1500)

        if login_type.lower() == "cjone":
            page.locator("a[href*='/account/login/cj-one']").first.click()
        else:
            page.locator("a[href*='/account/login/tving']").first.click()
        page.wait_for_timeout(1500)

        page.locator("input[name='id']").first.fill(username)
        page.locator("input[name='password']").first.fill(password)
        page.locator("button[type='submit'], button:has-text('로그인')").first.click()

        for _ in range(100):   # 최대 20초 대기
            page.wait_for_timeout(200)
            # 1. 팝업 자동 확인
            try:
                popup = page.locator("button:has-text('확인')").first
                if popup.is_visible():
                    popup.click()
                    page.wait_for_timeout(1000)
                    page.locator("button[type='submit']").first.click()
            except Exception:
                pass

            # 2. 다중 프로필 선택 화면 감지 및 자동 선택
            try:
                if "/account/profiles" in page.url or page.locator("text='프로필을 선택하세요'").first.is_visible():
                    btn = None
                    if target_profile:
                        btn = page.locator(
                            f"button:has-text('{target_profile}'), button:has(img[alt='{target_profile}'])"
                        ).first
                        if not btn.is_visible():
                            btn = None
                    if not btn:
                        btn = page.locator("button:has(img)").first

                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1500)
            except Exception:
                pass

            if captured:
                break
            if "/account/login" not in page.url and "tving.com" in page.url and "/account/profiles" not in page.url:
                for _ in range(15):
                    page.wait_for_timeout(200)
                    if captured:
                        break

        context.close()
        browser.close()

    if not captured:
        raise RuntimeError("profileNo를 찾지 못했습니다. 아이디, 비밀번호 또는 로그인 유형(티빙/CJ ONE)을 확인하세요.")

    body = captured[-1].get("body", {})
    profile = body.get("profile", {})
    profile_list = body.get("profileList", [])

    return {
        "profile_no":    profile.get("profileNo"),
        "profile_name":  profile.get("profileNm"),
        "profile_token": profile.get("profileToken"),
        "user_id":       body.get("userId"),
        "user_name":     body.get("userName"),
        "user_no":       body.get("userNo"),
        "all_profiles":  [
            {"profile_no": str(p.get("profileNo", "")), "profile_name": p.get("profileNm")}
            for p in profile_list
        ]
    }


def run_batch(file_path: str):
    """
    배치 검증 모드.
    accounts.json 형식:
    [
      {
        "id": "cbgg545",
        "password": "pw",
        "login_type": "cjone",                  # 선택사항: 'tving' (기본값) 또는 'cjone'
        "target_profile": "주여르",             # 선택사항: 대상 프로필명 (미지정 시 첫 번째 프로필 자동 선택)
        "expected_profile_no": "505135124",     # 필수: 기대 profileNo
        "desc": "계정 설명"
      }
    ]
    """
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            accounts = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 파일을 찾을 수 없습니다: {file_path}")
        print("        accounts.example.json을 참고하여 accounts.json을 생성하세요.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 파싱 실패: {e}")
        sys.exit(1)

    total = len(accounts)
    passed = failed = errors = 0
    results = []

    print()
    print("=" * 70)
    print(f"  TVING profileNo 배치 검증 시작 (총 {total}개 계정)")
    print("=" * 70)

    for i, account in enumerate(accounts, 1):
        user_id        = account.get("id", "")
        password       = account.get("password", "")
        login_type     = account.get("login_type", "tving")
        target_profile = account.get("target_profile")
        expected       = account.get("expected_profile_no", "")
        desc           = account.get("desc", "")

        type_info = f" [{login_type.upper()}]"
        target_info = f", 대상 프로필: '{target_profile}'" if target_profile else ""
        print(f"\n[{i}/{total}]{type_info} {user_id} ({desc}{target_info})")
        start = time.time()
        try:
            result       = extract_profile_no(
                user_id, password,
                target_profile=target_profile,
                login_type=login_type
            )
            actual       = result.get("profile_no", "")
            actual_name  = result.get("profile_name", "")
            all_profiles = result.get("all_profiles", [])
            elapsed      = round(time.time() - start, 2)

            if actual == expected:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"  상태        : {status}")
            print(f"  기대값      : {expected}")
            print(f"  실제값      : {actual} ({actual_name})")
            if len(all_profiles) > 1:
                profs_str = ", ".join([f"{p['profile_name']}({p['profile_no']})" for p in all_profiles])
                print(f"  보유 프로필 : {len(all_profiles)}개 [{profs_str}]")
            if status == "FAIL":
                print(f"  불일치 감지 : expected={expected}  /  actual={actual}")
            print(f"  소요 시간   : {elapsed}s")

            results.append({
                "id": user_id, "desc": desc, "status": status,
                "login_type": login_type,
                "expected": expected, "actual": actual,
                "profile_name": actual_name, "all_profiles": all_profiles,
                "elapsed": elapsed
            })
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            errors += 1
            print(f"  상태        : ERROR")
            print(f"  원인        : {e}")
            results.append({
                "id": user_id, "desc": desc, "status": "ERROR",
                "error": str(e), "elapsed": elapsed
            })

    print()
    print("=" * 70)
    print(f"  결과: {total}건 중  PASS {passed}  /  FAIL {failed}  /  ERROR {errors}")
    print("=" * 70)
    for r in results:
        mark = "O" if r["status"] == "PASS" else "X"
        pname = f" ({r.get('profile_name', '')})" if r.get("profile_name") else ""
        line = f"  [{mark}] {r['id']:<20}{pname:<12} | {r['status']}"
        if r["status"] == "FAIL":
            line += f"  (기대: {r['expected']} / 실제: {r['actual']})"
        elif r["status"] == "ERROR":
            line += f"  ({r.get('error','')[:40]})"
        print(line)
    print("=" * 70)
    print()

    if failed > 0 or errors > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="TVING 로그인 후 profileNo를 빠르게 추출하고 기대값과 비교 검증합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  티빙 아이디:   python quick.py -u xodn9900 -p "pw"
  CJ ONE 계정:   python quick.py -u cbgg545 -p "pw" --login-type cjone
  특정 프로필:   python quick.py -u cbgg545 -p "pw" --login-type cjone --profile "주여르"
  배치 검증:     python quick.py --file accounts.json
        """
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="아이디 (단일 모드)")
    parser.add_argument("-p", "--password", type=str, default=None, help="비밀번호 (단일 모드)")
    parser.add_argument("--login-type", choices=["tving", "cjone"], default="tving",
                        help="로그인 유형 선택: tving (티빙 아이디, 기본값) 또는 cjone (CJ ONE 아이디)")
    parser.add_argument("--profile", type=str, default=None, help="다중 프로필 계정 시 선택할 프로필 이름 (미지정 시 첫 번째 프로필 자동 선택)")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 출력 (단일 모드)")
    parser.add_argument("--file", type=str, default=None, metavar="accounts.json",
                        help="배치 검증 모드: 계정 목록 JSON 파일 경로")
    args = parser.parse_args()

    if args.file:
        run_batch(args.file)
        return

    username, password = get_credentials(args)
    start = time.time()
    result = extract_profile_no(
        username, password,
        target_profile=args.profile,
        login_type=args.login_type
    )
    elapsed = round(time.time() - start, 2)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"  profileNo    : {result['profile_no']}")
        print(f"  profile_name : {result['profile_name']}")
        print(f"  user_id      : {result['user_id']}")
        print(f"  user_name    : {result['user_name']}")
        all_profs = result.get("all_profiles", [])
        if len(all_profs) > 1:
            profs_str = ", ".join([f"{p['profile_name']}({p['profile_no']})" for p in all_profs])
            print(f"  보유 프로필  : {len(all_profs)}개 [{profs_str}]")
        print(f"  elapsed      : {elapsed}s")


if __name__ == "__main__":
    main()
