"""
MyPage POM extracting profileNo and related metadata via Network Interception of the TVING backend API.
"""
import logging
from typing import Optional, List, Tuple
from playwright.sync_api import Page, Response
from models import ProfileInfo
from .base_page import BasePage

logger = logging.getLogger("TVING_AUTO")


class MyPage(BasePage):
    MYPAGE_URL = "https://www.tving.com/my"
    TARGET_API_ENDPOINT = "api.tving.com/v2/user/info"

    def __init__(self, page: Page, timeout_ms: int = 30000):
        super().__init__(page, timeout_ms)
        self.captured_user_info_apis: List[dict] = []
        self._setup_network_interception()

    def _setup_network_interception(self):
        """TVING 백엔드 API 응답 가로채기(Network Interception) 리스너 등록"""
        def handle_response(response: Response):
            try:
                url = response.url
                if self.TARGET_API_ENDPOINT in url:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        body = response.json()
                        self.captured_user_info_apis.append(body)
                        logger.info("Network Intercept: TVING 유저 정보 API(/v2/user/info) 응답 포착 완료")
            except Exception:
                pass

        self.page.on("response", handle_response)

    # Selectors
    PROFILE_TRIGGER = "[data-testid='nav-profile-menu-trigger']"
    MY_MENU_LINK = "[data-testid='nav-profile-menu-my']"

    def navigate_to_mypage(self):
        """
        로그인 후 실제 사용자 행동과 동일하게 UI를 통해 마이페이지로 이동합니다.
        (프로필 아이콘 클릭/호버 -> 'MY' 메뉴 클릭)
        UI 탐색 실패 시 URL 직접 이동으로 자동 폴백합니다.
        """
        logger.info("마이페이지 진입 플로우 시작 (UI 프로필 메뉴 경유)...")

        try:
            # 1. 프로필 트리거 찾기
            trigger = self.page.locator(self.PROFILE_TRIGGER).first
            trigger.wait_for(state="visible", timeout=10000)
            logger.info(f"프로필 아이콘 클릭/호버: {self.PROFILE_TRIGGER}")
            trigger.hover()
            self.page.wait_for_timeout(300)
            trigger.click()
            self.page.wait_for_timeout(500)

            # 2. 드롭다운 메뉴 내 'MY' 링크 클릭
            my_link = self.page.locator(self.MY_MENU_LINK).first
            my_link.wait_for(state="visible", timeout=5000)
            logger.info(f"드롭다운 메뉴의 'MY' 클릭: {self.MY_MENU_LINK}")
            my_link.click()

            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            logger.info(f"마이페이지 UI 진입 성공: {self.page.url}")
        except Exception as e:
            logger.warning(f"UI 메뉴를 통한 이동 중 이슈 발생({e}). URL 직접 이동으로 폴백합니다.")
            self.navigate_to(self.MYPAGE_URL, wait_until="domcontentloaded")

    def extract_profile_from_api(self) -> Tuple[ProfileInfo, List[ProfileInfo]]:
        """
        가로챈 백엔드 API 응답(/v2/user/info)에서 profileNo 및 상세 프로필 정보를 추출합니다.
        
        Returns:
            (primary_profile, all_profiles)
        """
        logger.info("백엔드 API(/v2/user/info) 응답 데이터 파싱 시작...")

        # API 응답 도착 여부 대기 (최대 10초)
        for _ in range(50):
            if self.captured_user_info_apis:
                break
            self.page.wait_for_timeout(200)

        if not self.captured_user_info_apis:
            raise RuntimeError(
                f"TVING 유저 정보 API({self.TARGET_API_ENDPOINT}) 응답을 수신하지 못했습니다."
            )

        # 가장 최근 수신된 API 데이터부터 탐색
        for api_data in reversed(self.captured_user_info_apis):
            body = api_data.get("body", {})
            user_no = body.get("userNo")
            user_id = body.get("userId")
            user_name = body.get("userName")

            # 활성 프로필 정보
            active_profile = body.get("profile", {})
            profile_no = active_profile.get("profileNo")
            profile_name = active_profile.get("profileNm")
            profile_img = active_profile.get("profileImgPath")
            profile_token = active_profile.get("profileToken")  # API 인증 Bearer 토큰

            # 전체 프로필 목록
            profile_list_raw = body.get("profileList", [])
            all_profiles = []
            for p in profile_list_raw:
                all_profiles.append(ProfileInfo(
                    profile_no=str(p.get("profileNo", "")),
                    profile_name=p.get("profileNm"),
                    user_no=user_no,
                    user_id=user_id,
                    user_name=user_name,
                    profile_type=p.get("profileType"),
                    profile_image_path=p.get("profileImgPath"),
                    profile_token=p.get("profileToken")
                ))

            if profile_no:
                primary = ProfileInfo(
                    profile_no=str(profile_no),
                    profile_name=profile_name,
                    user_no=user_no,
                    user_id=user_id,
                    user_name=user_name,
                    profile_image_path=profile_img,
                    profile_token=profile_token
                )
                logger.info(f"API 추출 성공: profileNo={primary.profile_no}, 프로필명={primary.profile_name}")
                return primary, all_profiles

        raise RuntimeError(
            f"API 응답 내에 profileNo 필드가 존재하지 않습니다."
        )
