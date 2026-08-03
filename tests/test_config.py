import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Settings


class TestCorsAllowedOrigins:
    def test_wildcard_returns_wildcard_list(self):
        s = Settings(cors_allowed_origins="*")
        assert s.cors_allowed_origins_list == ["*"]

    def test_single_origin_returns_single_item_list(self):
        s = Settings(cors_allowed_origins="https://tripsync.vercel.app")
        assert s.cors_allowed_origins_list == ["https://tripsync.vercel.app"]

    def test_multiple_origins_split_and_trimmed(self):
        s = Settings(cors_allowed_origins="https://tripsync.vercel.app, http://localhost:5173 ,https://foo.com")
        assert s.cors_allowed_origins_list == [
            "https://tripsync.vercel.app",
            "http://localhost:5173",
            "https://foo.com",
        ]

    def test_defaults_to_wildcard(self):
        s = Settings()
        assert s.cors_allowed_origins_list == ["*"]
