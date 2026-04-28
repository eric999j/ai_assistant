"""clipboard_utils.is_safe_url / download_image (含 SSRF redirect 防護) 測試。"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pixel_assistant_app import clipboard_utils


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1/x.png", False),
        ("http://10.0.0.5/x.png", False),
        ("http://192.168.1.1/x.png", False),
        ("http://169.254.169.254/x.png", False),  # AWS metadata
        ("http://localhost/x.png", False),
        ("http://metadata.google.internal/x.png", False),
        ("http://example.com/x.png", True),
        ("https://cdn.example.com/x.png", True),
        ("ftp://example.com/x.png", False),  # 非 http(s)
        ("not-a-url", False),
        ("", False),
        ("http://server.local/x.png", False),  # internal-like
    ],
)
def test_is_safe_url(url, expected):
    assert clipboard_utils.is_safe_url(url) is expected


def test_looks_like_image_url():
    assert clipboard_utils.looks_like_image_url("https://x.com/a.png")
    assert clipboard_utils.looks_like_image_url("http://x.com/A.JPG")
    assert not clipboard_utils.looks_like_image_url("https://x.com/page")
    assert not clipboard_utils.looks_like_image_url("not-a-url")


class FakeResp:
    def __init__(self, status_code=200, headers=None, body=b"", chunk=65536):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body
        self._chunk = chunk
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def _make_png_bytes() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_download_image_blocks_redirect_to_internal(monkeypatch):
    """SSRF 修復重點：即使初始 URL 安全，若 302 跳轉到內網仍應被擋。"""
    calls = {"n": 0}

    def fake_get(url, timeout=10, stream=True, allow_redirects=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(status_code=302, headers={"Location": "http://127.0.0.1/secret"})
        pytest.fail("不應該對內網位址發出第二次請求")

    monkeypatch.setattr(clipboard_utils.requests, "get", fake_get)
    result = clipboard_utils.download_image("https://example.com/cat.png")
    assert result is None
    assert calls["n"] == 1


def test_download_image_follows_safe_redirect(monkeypatch):
    body = _make_png_bytes()

    def fake_get(url, timeout=10, stream=True, allow_redirects=False):
        if url == "https://example.com/start.png":
            return FakeResp(status_code=302, headers={"Location": "https://cdn.example.com/real.png"})
        if url == "https://cdn.example.com/real.png":
            return FakeResp(
                status_code=200,
                headers={"Content-Type": "image/png", "Content-Length": str(len(body))},
                body=body,
            )
        pytest.fail(f"unexpected url {url}")

    monkeypatch.setattr(clipboard_utils.requests, "get", fake_get)
    result = clipboard_utils.download_image("https://example.com/start.png")
    assert result is not None
    assert result.size == (4, 4)


def test_download_image_rejects_non_image_content_type(monkeypatch):
    def fake_get(url, timeout=10, stream=True, allow_redirects=False):
        return FakeResp(status_code=200, headers={"Content-Type": "text/html"}, body=b"<html/>")

    monkeypatch.setattr(clipboard_utils.requests, "get", fake_get)
    assert clipboard_utils.download_image("https://example.com/x.png") is None


def test_download_image_size_limit(monkeypatch):
    big = b"x" * (clipboard_utils.MAX_IMAGE_BYTES + 100)

    def fake_get(url, timeout=10, stream=True, allow_redirects=False):
        return FakeResp(
            status_code=200,
            headers={"Content-Type": "image/png", "Content-Length": str(len(big))},
            body=big,
        )

    monkeypatch.setattr(clipboard_utils.requests, "get", fake_get)
    assert clipboard_utils.download_image("https://example.com/x.png") is None


def test_download_image_refuses_unsafe_initial_url(monkeypatch):
    def fail_get(*a, **kw):
        pytest.fail("不該發出請求")

    monkeypatch.setattr(clipboard_utils.requests, "get", fail_get)
    assert clipboard_utils.download_image("http://127.0.0.1/x.png") is None
