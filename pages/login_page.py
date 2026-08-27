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
    CJONE_ID_LINK = "a[href*='/account/login/cj-one']"
    ID_INPUT = "input[name='id']"
    PW_INPUT = "input[name='password']"
    SUBMIT_BTN = "button[type='submit']"

    # Error modal selectors
    MODAL_TEXT = "div:has-text('입력하신 회원정보를 찾을 수 없습니다'), div:has-text('일시적인 서비스 오류'), div:has-text('오류')"

    def open_via_flow(self, login_type: str = "tving"):
        """
        메인 페이지 진입 후 로그인 경로(티빙 ID 또는 CJ ONE)로 이동합니다.
        """
        logger.info("메인 페이지 진입 및 로그인 경로 탐색...")
        self.navigate_to(self.MAIN_URL, wait_until="domcontentloaded")

        logger.info(f"메인 페이지의 로그인 버튼 클릭 (Selector: {self.NAV_LOGIN_BTN})")
        self.safe_click(self.NAV_LOGIN_BTN)
        self.page.wait_for_load_state("domcontentloaded")

        if login_type.lower() == "cjone":
            logger.info(f"'CJ ONE으로 시작하기' 옵션 선택 (Selector: {self.CJONE_ID_LINK})")
            self.safe_click(self.CJONE_ID_LINK)
        else:
            logger.info(f"'티빙 아이디로 로그인' 옵션 선택 (Selector: {self.TVING_ID_LINK})")
            self.safe_click(self.TVING_ID_LINK)

        try:
            self.page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

    def perform_login(self, username: str, password: str, target_profile: Optional[str] = None) -> bool:
        """
        아이디와 비밀번호를 입력하고 로그인을 수행합니다.
        다중 프로필 계정일 경우 지정된 프로필(또는 첫 번째 프로필)을 자동 선택합니다.
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
        for attempt in range(45):  # 최대 9초 대기
            self.page.wait_for_timeout(200)

            # 1. 로그인 성공 감지 (로그인 페이지를 벗어났는지 확인)
            try:
                current_url = self.page.url
                if "/account/login" not in current_url:
                    logger.info("로그인 인증 성공!")

                    # 1-1. 다중 프로필 선택 화면 자동 처리
                    self.handle_profile_selection(target_profile)

                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
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

                    raise RuntimeError(f"로그인 실패: {err_msg}")
            except RuntimeError:
                raise
            except Exception:
                pass

        raise RuntimeError("로그인 후 응답 대기 시간 초과")

    def handle_profile_selection(self, target_profile: Optional[str] = None) -> bool:
        """
        다중 프로필 계정의 경우 로그인 직후 나타나는 '프로필을 선택하세요' 화면을 감지하고 프로필을 선택합니다.
        - target_profile이 지정되어 있으면 해당 프로필 클릭
        - 미지정 시 첫 번째(기본) 프로필 자동 클릭
        - 단일 프로필 계정이라 선택 화면이 없으면 자동으로 통과
        """
        self.page.wait_for_timeout(1000)
        current_url = self.page.url

        # 프로필 선택 화면 여부 확인
        is_profiles_page = (
            "/account/profiles" in current_url
            or self.page.locator("text='프로필을 선택하세요'").first.is_visible()
        )

        if not is_profiles_page:
            return False

        logger.info(f"다중 프로필 선택 화면 감지. 프로필 선택 진행 (지정 프로필: {target_profile or '첫 번째(기본)'})")

        btn = None
        if target_profile:
            btn = self.page.locator(
                f"button:has-text('{target_profile}'), button:has(img[alt='{target_profile}'])"
            ).first
            if not btn.is_visible():
                logger.warning(f"지정된 프로필 '{target_profile}'을 찾을 수 없어 첫 번째 프로필을 선택합니다.")
                btn = None

        if not btn:
            # 첫 번째 프로필 카드 버튼
            btn = self.page.locator("button:has(img)").first

        if btn and btn.is_visible():
            btn_text = btn.inner_text().replace("\n", " ").strip()
            logger.info(f"프로필 카드 자동 선택 완료: '{btn_text}'")
            btn.click()
            self.page.wait_for_timeout(2000)
            return True
        else:
            logger.warning("프로필 선택 버튼을 찾지 못했습니다.")
            return False

