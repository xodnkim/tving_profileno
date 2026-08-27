"""
Configuration manager supporting interactive CLI prompt and optional command-line arguments.
"""
import os
import getpass
from typing import Optional


class Config:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
        timeout_ms: int = 30000,
        output_path: Optional[str] = None,
        target_profile: Optional[str] = None,
        login_type: str = "tving"
    ):
        self.login_type = login_type.lower().strip() if login_type else "tving"
        self.target_profile = target_profile.strip() if target_profile else None
        # 1. Username: CLI 인자 우선, 없으면 대화형 터미널 입력
        if username:
            self.username = username.strip()
        else:
            print("[1/2] TVING 아이디를 입력해주세요: ", end="", flush=True)
            self.username = input().strip()

        # 2. Password: CLI 인자 우선, 없으면 대화형 마스킹 터미널 입력
        if password:
            self.password = password.strip()
        else:
            self.password = getpass.getpass("[2/2] TVING 비밀번호를 입력해주세요 (화면에 표시되지 않음): ").strip()

        self.headless = headless
        self.timeout_ms = timeout_ms
        self.output_path = output_path

    def __repr__(self) -> str:
        masked_pw = "*" * len(self.password) if self.password else "None"
        return f"Config(username={self.username}, password={masked_pw}, headless={self.headless})"
