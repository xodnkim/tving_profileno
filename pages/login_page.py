"""
LoginPage POM encapsulating TVING ID login actions and error handling.
"""
import logging
from typing import Tuple, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from .base_page import BasePage

logger = logging.getLogger("TVING_AUTO")

class LoginPage(BasePage):
    MAIN_URL = "https://www.tving.com/"

    # Selectors (QA/E2E 테스트 표준: data-testid 우선 적용)
    NAV_LOGIN_BTN = "[data-testid='nav-login-button']"
    TVING_ID_LINK = "a[href*='/account/login/tving']"
    ID_INPUT = "input[name='id']"
    PW_INPUT = "input[name='password']"
    SUBMIT_BTN = "button[type='submit']"

    # Error modal selectors
    MODAL_TEXT = "div:has-text('입력하신 회원정보를 찾을 수 없습니다'), div:has-text('일시적인 서비스 오류'), div:has-text('오류')"

    def open_via_flow(self):
        """메인 페이지 진입 후 '로그인' -> '티빙 아이디로 로그인' 경로로 이동합니다."""
        logger.info("메인 페이지 진입 및 로그인 경로 탐색...")
        self.navigate_to(self.MAIN_URL, wait_until="domcontentloaded")

        logger.info(f"메인 페이지의 로그인 버튼 클릭 (Selector: {self.NAV_LOGIN_BTN})")
        self.safe_click(self.NAV_LOGIN_BTN)
        self.page.wait_for_load_state("domcontentloaded")

        logger.info(f"'티빙 아이디로 로그인' 옵션 선택 (Selector: {self.TVING_ID_LINK})")
        self.safe_click(self.TVING_ID_LINK)
        try:
            self.page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

    def perform_login(self, username: str, password: str) -> bool:
        """
        아이디와 비밀번호를 입력하고 로그인을 수행합니다.
        """
        logger.info(f"로그인 시도 - 사용자 ID: {username}")

        # 입력창 대기
        try:
            self.page.locator(self.ID_INPUT).first.wait_for(state="visible", timeout=self.timeout_ms)
        except PlaywrightTimeoutError:
            raise RuntimeError("아이디 입력창을 찾을 수 없습니다.")

        # 자연스러운 입력 및 딜레이
        self.page.wait_for_timeout(300)
        self.safe_fill(self.ID_INPUT, username)
        self.page.wait_for_timeout(200)
        self.safe_fill(self.PW_INPUT, password)
        self.page.wait_for_timeout(300)

        # 로그인 버튼 클릭
        self.safe_click(self.SUBMIT_BTN)

        # 결과 대기 (성공적인 페이지 전환 또는 에러 모달 출현 감지)
        for attempt in range(35):  # 최대 7초 대기
            self.page.wait_for_timeout(200)

            # 1. 로그인 성공 감지 (로그인 페이지를 벗어났는지 확인)
            try:
                current_url = self.page.url
                if "/account/login" not in current_url:
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    logger.info("로그인 성공!")
                    return True
            except Exception:
                continue

            # 2. 에러 모달 감지
            try:
                modal = self.page.locator(self.MODAL_TEXT).first
                if modal.count() > 0 and modal.is_visible():
                    err_msg = modal.inner_text().replace("\n", " ")
                    # 만약 일시적인 서비스 오류인 경우, 확인을 누르고 1회 재클릭 시도
                    if "일시적인 서비스 오류" in err_msg and attempt < 15:
                        logger.warning("일시적인 서비스 오류 팝업 감지. 확인 후 1.5초 뒤 재시도합니다...")
                        confirm_btn = self.page.locator("button:has-text('확인')").first
                        if confirm_btn.count() > 0:
                            confirm_btn.click()
                        self.page.wait_for_timeout(1500)
                        self.safe_click(self.SUBMIT_BTN)
                        continue

                    screenshot_path = self.take_screenshot("login_failed")
                    raise RuntimeError(f"로그인 실패: {err_msg} (스크린샷: {screenshot_path})")
            except RuntimeError:
                raise
            except Exception:
                pass

        screenshot_path = self.take_screenshot("login_timeout")
        raise RuntimeError(f"로그인 후 응답 대기 시간 초과 (스크린샷: {screenshot_path})")
