"""
quick.py - 가장 빠르게 profileNo를 추출하고 기대값과 비교 검증하는 스크립트

[단일 계정 모드]
  python quick.py                          # 대화형 입력
  python quick.py -u xodn9900 -p "pw"     # CLI 인자
  python quick.py -u xodn9900 -p "pw" --json  # JSON 출력

[배치 검증 모드] --file 옵션
  python quick.py --file accounts.json
  -> JSON 파일에 기재된 계정 목록을 순회하며 실제 profileNo를 추출하고
     DB에서 확보한 expected_profile_no와 비교하여 PASS/FAIL 리포트를 출력합니다.

  사용 사례:
    - 정기 헬스체크: 사내 테스트 계정들의 profileNo 매핑이 정상인지 매일 새벽 전수 검증
    - 배포 후 스모크 테스트: 신규 배포 후 핵심 계정들의 인증 흐름이 정상인지 빠르게 검증

  ※ expected_profile_no는 반드시 DB에서 직접 확인한 값을 수동 기입합니다.
     (시스템이 자동 생성한 값으로 검증하면 버그도 함께 통과하는 잘못된 테스트가 됩니다.)
"""

import sys
import io
import time
import json
import getpass
import argparse

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
        print("[1/2] TVING 아이디: ", end="", flush=True)
        username = input().strip()
    if not password:
        password = getpass.getpass("[2/2] 비밀번호 (입력 안 보임): ").strip()
    return username, password


def extract_profile_no(username: str, password: str) -> dict:
    """
    핵심 함수: 로그인 후 /v2/user/info API를 가로채 profileNo를 반환.
    마이페이지 이동 없이 로그인 직후 즉시 종료.
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

        # 메인 페이지 -> 로그인 버튼 -> 티빙 아이디로 로그인
        # (URL 직접 이동 금지: deviceId/보안 토큰 미발급으로 서버 오류 발생)
        page.goto("https://www.tving.com/", wait_until="domcontentloaded")
        page.locator("[data-testid='nav-login-button']").first.click()
        page.wait_for_timeout(1500)
        page.locator("a[href*='/account/login/tving']").first.click()
        page.wait_for_timeout(1500)

        page.locator("input[name='id']").first.fill(username)
        page.locator("input[name='password']").first.fill(password)
        page.locator("button[type='submit']").first.click()

        for _ in range(100):   # 최대 20초 대기
            page.wait_for_timeout(200)
            try:
                popup = page.locator("button:has-text('확인')").first
                if popup.is_visible():
                    popup.click()
                    page.wait_for_timeout(1000)
                    page.locator("button[type='submit']").first.click()
            except Exception:
                pass
            if captured:
                break
            if "/account/login" not in page.url and "tving.com" in page.url:
                for _ in range(15):
                    page.wait_for_timeout(200)
                    if captured:
                        break

        context.close()
        browser.close()

    if not captured:
        raise RuntimeError("profileNo를 찾지 못했습니다. 아이디/비밀번호를 확인하세요.")

    body = captured[-1].get("body", {})
    profile = body.get("profile", {})
    return {
        "profile_no":    profile.get("profileNo"),
        "profile_name":  profile.get("profileNm"),
        "profile_token": profile.get("profileToken"),
        "user_id":       body.get("userId"),
        "user_name":     body.get("userName"),
        "user_no":       body.get("userNo"),
    }


def run_batch(file_path: str):
    """
    배치 검증 모드.
    accounts.json 형식:
    [
      {
        "id": "test_account_01",
        "password": "pw1234",
        "expected_profile_no": "511756099",
        "desc": "계정 설명"
      }
    ]
    expected_profile_no는 DB에서 직접 확인한 값을 수동 기입합니다.
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
    print("=" * 65)
    print(f"  TVING profileNo 배치 검증 시작 (총 {total}개 계정)")
    print("=" * 65)

    for i, account in enumerate(accounts, 1):
        user_id  = account.get("id", "")
        password = account.get("password", "")
        expected = account.get("expected_profile_no", "")
        desc     = account.get("desc", "")

        print(f"\n[{i}/{total}] {user_id} ({desc})")
        start = time.time()
        try:
            result  = extract_profile_no(user_id, password)
            actual  = result.get("profile_no", "")
            elapsed = round(time.time() - start, 2)

            if actual == expected:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"  상태   : {status}")
            print(f"  기대값 : {expected}")
            print(f"  실제값 : {actual}")
            if status == "FAIL":
                print(f"  차이   : expected={expected}  /  actual={actual}  <-- 불일치 감지!")
            print(f"  소요   : {elapsed}s")

            results.append({"id": user_id, "desc": desc, "status": status,
                             "expected": expected, "actual": actual, "elapsed": elapsed})
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            errors += 1
            print(f"  상태   : ERROR")
            print(f"  원인   : {e}")
            results.append({"id": user_id, "desc": desc, "status": "ERROR",
                             "error": str(e), "elapsed": elapsed})

    print()
    print("=" * 65)
    print(f"  결과: {total}건 중  PASS {passed}  /  FAIL {failed}  /  ERROR {errors}")
    print("=" * 65)
    for r in results:
        mark = "O" if r["status"] == "PASS" else "X"
        line = f"  [{mark}] {r['id']:<22} | {r['status']}"
        if r["status"] == "FAIL":
            line += f"  (기대: {r['expected']} / 실제: {r['actual']})"
        elif r["status"] == "ERROR":
            line += f"  ({r.get('error','')[:45]})"
        print(line)
    print("=" * 65)
    print()

    # FAIL/ERROR 존재 시 exit code 1 반환 (CI/CD 파이프라인 자동 감지용)
    if failed > 0 or errors > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="TVING 로그인 후 profileNo를 빠르게 추출하고 기대값과 비교 검증합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  단일 계정:  python quick.py -u xodn9900 -p "pw"
  배치 검증:  python quick.py --file accounts.json
        """
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="TVING 아이디 (단일 모드)")
    parser.add_argument("-p", "--password", type=str, default=None, help="TVING 비밀번호 (단일 모드)")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 출력 (단일 모드)")
    parser.add_argument("--file", type=str, default=None, metavar="accounts.json",
                        help="배치 검증 모드: 계정 목록 JSON 파일 경로")
    args = parser.parse_args()

    if args.file:
        run_batch(args.file)
        return

    username, password = get_credentials(args)
    start = time.time()
    result = extract_profile_no(username, password)
    elapsed = round(time.time() - start, 2)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"  profileNo    : {result['profile_no']}")
        print(f"  profile_name : {result['profile_name']}")
        print(f"  user_id      : {result['user_id']}")
        print(f"  elapsed      : {elapsed}s")


if __name__ == "__main__":
    main()
