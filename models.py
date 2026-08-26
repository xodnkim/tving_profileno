"""
Data models for TVING profile extraction automation.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ProfileInfo:
    """Represents profile data extracted from TVING API."""
    profile_no: str                             # 프로필 고유 식별자 (과제 핵심 목표)
    profile_name: Optional[str] = None          # 프로필 이름 (예: "기본프로필")
    user_no: Optional[str] = None               # 계정(회원) 번호
    user_id: Optional[str] = None              # 로그인 아이디
    user_name: Optional[str] = None             # 실명
    profile_type: Optional[str] = None          # 프로필 유형 (일반/키즈 등)
    profile_image_path: Optional[str] = None    # 프로필 이미지 URL
    profile_token: Optional[str] = None         # API 인증에 사용되는 Bearer 토큰

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



@dataclass
class ExtractionResult:
    """Result of the overall extraction process."""
    success: bool
    profile: Optional[ProfileInfo] = None
    all_profiles: List[ProfileInfo] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
