"""
quick.py - 가장 빠르게 profileNo만 뽑는 단일 파일 스크립트

main.py와의 차이:
  - 마이페이지 이동 없음 (로그인 직후 API 응답 포착으로 즉시 종료)
  - POM 구조 없이 단일 파일로 완결
  - 출력은 profileNo 하나만 stdout으로
  - 소요 시간: 약 10~13초 (main.py 대비 ~50% 단축)

사용법:
  python quick.py                          # 대화형 입력
  python quick.py -u xodn9900 -p "pw"     # CLI 인자
  python quick.py -u xodn9900 -p "pw" --json  # JSON 출력
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


def get_credentials(args: argparse.Namespace):
    """CLI 인자가 있으면 그대로 쓰고, 없으면 대화형 입력."""
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
    핵심 함수: 로그인 후 발생하는 /v2/user/info API를 가로채 profileNo를 반환.
    마이페이지 이동 없이 로그인 직후 즉시 종료.

    Returns:
        dict: {"profile_no": str, "profile_name": str, "profile_token": str, ...}
    """
    captured: list[dict] = []   # API 응답을 담을 버킷

    with sync_playwright() as p:
        # 1. 브라우저 기동 (항상 headless - 속도 우선)
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

        # 2. Network Interception 리스너 등록
        #    브라우저가 받는 모든 HTTP 응답 중 /v2/user/info만 필터해서 captured에 저장
        def on_response(response: Response):
            try:
                if TARGET_API in response.url:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        captured.append(response.json())
            except Exception:
                pass

        page.on("response", on_response)

        # 3. 메인 페이지 → 로그인 버튼 → 티빙 아이디로 로그인
        #    (URL 직접 이동 금지: deviceId/보안 토큰 미발급으로 서버 오류 발생)
        page.goto("https://www.tving.com/", wait_until="domcontentloaded")
        page.locator("[data-testid='nav-login-button']").first.click()
        page.wait_for_timeout(1500)
        page.locator("a[href*='/account/login/tving']").first.click()
        page.wait_for_timeout(1500)

        # 4. ID / PW 입력 & 제출
        page.locator("input[name='id']").first.fill(username)
        page.locator("input[name='password']").first.fill(password)
        page.locator("button[type='submit']").first.click()

        # 5. 로그인 결과 대기 (최대 20초)
        #    - /v2/user/info API가 포착되거나
        #    - URL이 로그인 페이지를 벗어나면 성공으로 판단
        for _ in range(100):   # 100 × 200ms = 20초
            page.wait_for_timeout(200)

            # 일시적 서비스 오류 팝업 자동 닫기
            try:
                popup = page.locator("button:has-text('확인')").first
                if popup.is_visible():
                    popup.click()
                    page.wait_for_timeout(1000)
                    page.locator("button[type='submit']").first.click()
            except Exception:
                pass

            # API 포착 완료 시 즉시 종료 (마이페이지 이동 불필요)
            if captured:
                break

            # 로그인 완료 감지 (URL 변화 감지)
            if "/account/login" not in page.url and "tving.com" in page.url:
                # URL은 벗어났지만 API 아직 안 왔으면 조금 더 대기
                for _ in range(15):   # 추가 3초
                    page.wait_for_timeout(200)
                    if captured:
                        break

        context.close()
        browser.close()

    # 6. API 응답 파싱
    if not captured:
        raise RuntimeError(
            "profileNo를 찾지 못했습니다. 아이디/비밀번호를 확인하거나 "
            "--no-headless 옵션으로 실행하여 브라우저 화면을 직접 확인하세요."
        )

    body = captured[-1].get("body", {})   # 가장 최근 응답 사용
    profile = body.get("profile", {})

    return {
        "profile_no":    profile.get("profileNo"),
        "profile_name":  profile.get("profileNm"),
        "profile_token": profile.get("profileToken"),
        "user_id":       body.get("userId"),
        "user_name":     body.get("userName"),
        "user_no":       body.get("userNo"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="TVING 로그인 후 profileNo를 가장 빠르게 추출합니다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="TVING 아이디")
    parser.add_argument("-p", "--password", type=str, default=None, help="TVING 비밀번호")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 형식으로 출력")
    args = parser.parse_args()

    username, password = get_credentials(args)

    start = time.time()
    result = extract_profile_no(username, password)
    elapsed = round(time.time() - start, 2)

    if args.json:
        # CI/CD 파이프라인에서 파싱하기 쉽게 JSON으로 출력
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"  profileNo    : {result['profile_no']}")
        print(f"  profile_name : {result['profile_name']}")
        print(f"  user_id      : {result['user_id']}")
        print(f"  elapsed      : {elapsed}s")


if __name__ == "__main__":
    main()
