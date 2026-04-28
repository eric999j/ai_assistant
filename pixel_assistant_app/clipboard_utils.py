"""剪貼簿與圖片 URL 安全工具，與 UI 解耦以便單獨測試。"""
from __future__ import annotations

import ipaddress
import logging
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")


def is_safe_url(url: str) -> bool:
    """檢查 URL 是否指向安全的外部位址（阻擋 private/loopback IP 以防 SSRF）。"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            addr = ipaddress.ip_address(hostname)
            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_reserved
                or addr.is_link_local
                or addr.is_multicast
                or addr.is_unspecified
            ):
                return False
        except ValueError:
            lower_host = hostname.lower()
            if lower_host in ("localhost", "metadata.google.internal"):
                return False
            if lower_host.endswith(".local") or lower_host.endswith(".internal"):
                return False
        return True
    except Exception:
        return False


def looks_like_image_url(text: str) -> bool:
    if not text or not text.startswith("http"):
        return False
    return any(text.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


def download_image(url: str, max_bytes: int = MAX_IMAGE_BYTES, timeout: int = 10) -> Image.Image | None:
    """安全下載圖片：阻擋 SSRF（含 redirect target）、限制大小、驗證 Content-Type。

    回傳 PIL Image，失敗時回傳 None。
    """
    if not is_safe_url(url):
        logger.warning("Refused to fetch unsafe URL: %s", url)
        return None

    try:
        # 關閉自動 redirect 以便逐步驗證每個跳轉目標
        current_url = url
        for _ in range(5):  # 最多跟 5 次跳轉
            resp = requests.get(
                current_url, timeout=timeout, stream=True, allow_redirects=False
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                next_url = resp.headers.get("Location")
                resp.close()
                if not next_url:
                    return None
                # 處理相對路徑
                from urllib.parse import urljoin
                next_url = urljoin(current_url, next_url)
                if not is_safe_url(next_url):
                    logger.warning("Redirect target unsafe: %s", next_url)
                    return None
                current_url = next_url
                continue
            if resp.status_code != 200:
                resp.close()
                return None
            break
        else:
            logger.warning("Too many redirects: %s", url)
            return None

        try:
            c_type = resp.headers.get("Content-Type", "").lower()
            if "image" not in c_type:
                return None
            content_length = int(resp.headers.get("Content-Length", 0) or 0)
            if content_length and content_length > max_bytes:
                logger.info("Image too large (Content-Length=%d)", content_length)
                return None
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > max_bytes:
                    logger.info("Image exceeded max bytes during download")
                    return None
                chunks.append(chunk)
            if not chunks:
                return None
            return Image.open(BytesIO(b"".join(chunks)))
        finally:
            resp.close()
    except Exception as e:
        logger.error("download_image failed: %s", e)
        return None
