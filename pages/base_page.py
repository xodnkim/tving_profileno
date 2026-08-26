"""
Base Page Object providing common utilities, wait helpers, and screenshot capabilities.
"""
import os
import logging
from datetime import datetime
from typing import Optional
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("TVING_AUTO")


class BasePage:
    def __init__(self, page: Page, timeout_ms: int = 30000):
        self.page = page
        self.timeout_ms = timeout_ms

    def navigate_to(self, url: str, wait_until: str = "networkidle"):
        logger.info(f"페이지 이동: {url}")
        self.page.goto(url, wait_until=wait_until, timeout=self.timeout_ms)

    def safe_click(self, selector: str, timeout_ms: Optional[int] = None) -> bool:
        """안전하게 요소를 찾아 클릭합니다."""
        to = timeout_ms or self.timeout_ms
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=to)
            loc.click()
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"클릭 실패 (요소를 찾을 수 없거나 타임아웃): {selector}")
            return False

    def safe_fill(self, selector: str, value: str, timeout_ms: Optional[int] = None) -> bool:
        """안전하게 입력 필드를 찾아 값을 입력합니다."""
        to = timeout_ms or self.timeout_ms
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=to)
            loc.click()
            loc.fill(value)
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"입력 실패 (요소를 찾을 수 없거나 타임아웃): {selector}")
            return False

    def take_screenshot(self, name_prefix: str = "capture") -> str:
        """
        artifacts/screenshots 디렉토리에 타임스탬프와 함께 스크린샷을 저장합니다.
        """
        screenshots_dir = os.path.join(os.getcwd(), "artifacts", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)

        try:
            self.page.screenshot(path=filepath, full_page=False)
            logger.info(f"스크린샷 저장 완료: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {e}")
            return ""

    def get_cookie_value(self, name: str) -> Optional[str]:
        """현재 컨텍스트의 특정 쿠키 값을 가져옵니다."""
        for cookie in self.page.context.cookies():
            if cookie["name"] == name:
                return cookie["value"]
        return None
