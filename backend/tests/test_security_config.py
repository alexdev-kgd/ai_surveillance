import importlib.util
import asyncio
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


CONFIG = Path(__file__).resolve().parents[1] / "core" / "config.py"


def read_config(env):
    spec = importlib.util.spec_from_file_location("security_config_under_test", CONFIG)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv"):
        spec.loader.exec_module(module)
    return module


class SecurityConfigTests(unittest.TestCase):
    def test_missing_short_and_old_keys_fail(self):
        for key in ("", "short", "AIS_AI_SECRET_KEY"):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                read_config({"SECRET_KEY": key})

    def test_external_key_is_preserved_and_cors_defaults_closed(self):
        config = read_config({"SECRET_KEY": "a" * 48})
        self.assertEqual(config.SECRET_KEY, "a" * 48)
        self.assertEqual(config.CORS_ORIGINS, [])

    def test_invalid_origins_fail(self):
        for origin in ("*", "https://*.example.com", "null", "https://example.com/path",
                       "https://user:pass@example.com", "https://example.com:bad"):
            with self.subTest(origin=origin), self.assertRaises((RuntimeError, ValueError)):
                read_config({"SECRET_KEY": "a" * 48, "CORS_ORIGINS": origin})

    def test_browser_preflight_allows_only_configured_origin(self):
        config = read_config({"SECRET_KEY": "a" * 48,
                              "CORS_ORIGINS": "https://ui.example.com"})
        app = FastAPI()
        app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                           allow_credentials=True,
                           allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                           allow_headers=["Authorization", "Content-Type"])
        for origin, status in (("https://ui.example.com", 200),
                               ("https://attacker.example.com", 400)):
            messages = []
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(message):
                messages.append(message)
            asyncio.run(app({"type": "http", "method": "OPTIONS", "path": "/",
                "headers": [(b"origin", origin.encode()),
                            (b"access-control-request-method", b"POST"),
                            (b"access-control-request-headers", b"authorization,content-type")]},
                receive, send))
            response = messages[0]
            self.assertEqual(response["status"], status)
            self.assertEqual(dict(response["headers"]).get(b"access-control-allow-origin"),
                             origin.encode() if status == 200 else None)


if __name__ == "__main__":
    unittest.main()
