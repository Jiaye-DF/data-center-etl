"""測試共用前置:get_settings 為 lru_cache(scan AD-007),各測試檔的 env 注入
時點不同(檔頭 os.environ 設定),每個測試前清快取確保讀到該檔期望的 env。
"""

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
