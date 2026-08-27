"""
TVING Profile Automation CLI Entrypoint.
Interactive CLI input + Network Interception API Extraction.
"""
import os
import sys
import io
import time
import json
import logging
import argparse
from typing import Optional

# Windows 콘솔 한글/유니코드 인코딩 보정
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

from config import Config
from models import ProfileInfo, ExtractionResult
from pages import LoginPage, MyPage

# 로깅 포맷 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TVING_AUTO")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TVING 자동 로그인 및 profileNo API 추출 자동화 도구",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="TVING 아이디 (생략 시 터미널에서 직접 입력)")
    parser.add_argument("-p", "--password", type=str, default=None, help="TVING 비밀번호 (생략 시 터미널에서 마스킹 입력)")
    parser.add_argument("--headless", action="store_true", default=True, help="헤드리스 모드로 실행 (기본값)")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="브라우저 화면을 보면서 실행")
    parser.add_argument("-o", "--output", type=str, help="결과를 저장할 JSON 파일 경로")
    parser.add_argument("--profile", type=str, default=None, help="다중 프로필 계정 시 선택할 프로필 이름 (미지정 시 첫 번째 프로필 자동 선택)")
    parser.add_argument("--login-type", choices=["tving", "cjone"], default="tving",
                        help="로그인 유형 선택: tving (티빙 아이디, 기본값) 또는 cjone (CJ ONE 아이디)")
    return parser.parse_args()


def run_automation(config: Config) -> ExtractionResult:
    start_time = time.time()
    result = ExtractionResult(success=False)

    with sync_playwright() as p:
        logger.info(f"브라우저 기동 (Headless: {config.headless})...")
        browser = p.chromium.launch(headless=config.headless)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        page = context.new_page()

        try:
            # 1. Page Objects 초기화
            login_page = LoginPage(page, timeout_ms=config.timeout_ms)
            my_page = MyPage(page, timeout_ms=config.timeout_ms)

            # 2. 메인 페이지 -> 로그인 플로우 수행 (deviceId 세션 보장)
            login_page.open_via_flow(login_type=config.login_type)

            # 3. 로그인 수행 (다중 프로필 계정 시 자동 선택 지원)
            login_page.perform_login(
                username=config.username,
                password=config.password,
                target_profile=config.target_profile
            )

            # 4. 마이페이지 진입
            my_page.navigate_to_mypage()

            # 5. 백엔드 API 응답 가로채기(/v2/user/info)를 통한 profileNo 추출
            primary_profile, all_profiles = my_page.extract_profile_from_api()

            elapsed = round(time.time() - start_time, 2)
            result.success = True
            result.profile = primary_profile
            result.all_profiles = all_profiles
            result.elapsed_seconds = elapsed

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            logger.error(f"자동화 수행 중 오류 발생: {e}")
            result.success = False
            result.error_message = str(e)
            result.elapsed_seconds = elapsed
        finally:
            context.close()
            browser.close()

    return result


def print_summary(result: ExtractionResult):
    """콘솔 요약 리포트 출력"""
    print("\n" + "=" * 60)
    if result.success and result.profile:
        p = result.profile
        print("          🎉 TVING profileNo 추출 성공! 🎉")
        print("=" * 60)
        print(f" [★] profileNo       : {p.profile_no}")
        print(f" [-] 프로필 명       : {p.profile_name or 'N/A'}")
        print(f" [-] 사용자 ID       : {p.user_id or 'N/A'}")
        print(f" [-] 사용자 명       : {p.user_name or 'N/A'}")
        print(f" [-] 회원 번호(userNo): {p.user_no or 'N/A'}")
        print(f" [-] 데이터 출처     : 백엔드 API (/v2/user/info)")
        print(f" [-] 총 소요 시간    : {result.elapsed_seconds}초")
        if len(result.all_profiles) > 1:
            print(f" [-] 보유 프로필 목록 ({len(result.all_profiles)}개):")
            for idx, ap in enumerate(result.all_profiles, 1):
                print(f"       {idx}. {ap.profile_name} (profileNo: {ap.profile_no})")
    else:
        print("          ❌ TVING profileNo 추출 실패 ❌")
        print("=" * 60)
        print(f" [-] 에러 원인: {result.error_message}")
        print(f" [-] 총 소요 시간: {result.elapsed_seconds}초")
    print("=" * 60 + "\n")


def main():
    args = parse_arguments()

    print("=" * 60)
    print("      🎬 TVING 자동 로그인 & profileNo 추출 프로그램")
    print("=" * 60)

    # CLI 인자 또는 순차적 프롬프트 입력
    config = Config(
        username=args.username,
        password=args.password,
        headless=args.headless,
        output_path=args.output,
        target_profile=args.profile,
        login_type=args.login_type
    )

    # 실행
    result = run_automation(config)

    # 결과 출력
    print_summary(result)

    # JSON 저장 처리
    if config.output_path:
        with open(config.output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"결과 JSON 파일 저장 완료: {config.output_path}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
