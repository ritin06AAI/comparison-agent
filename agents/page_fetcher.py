import os
import requests
from utils.logger import setup_logger
from typing import Optional

logger = setup_logger(__name__)


class PageFetcher:
    def __init__(self, headless=True, timeout=30000):
        self.headless = headless
        self.timeout = timeout / 1000  # ms -> seconds

    def fetch_html(self, url: str, auth_type: Optional[str] = None, credentials: str = "") -> str:
        """
        Fetch page HTML using requests, with optional basic auth.
        auth_type: None or 'basic'
        credentials: 'user:pass'
        """
        try:
            logger.info(f"Fetching URL (requests): {url}")

            auth = None
            if auth_type == "basic" and ":" in credentials:
                user, pwd = credentials.split(":", 1)
                auth = (user, pwd)

            resp = requests.get(url, timeout=self.timeout, auth=auth)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Error fetching {url} via requests: {e}")
            raise

    def take_screenshot(
        self,
        url: str,
        save_path: str,
        auth_type: Optional[str] = None,
        credentials: str = "",
    ) -> Optional[str]:
        """
        Take a full-page screenshot of the URL using Playwright.
        Returns the saved screenshot path, or None if it fails.

        save_path: full file path where the .png should be saved, e.g. 'reports/screenshots/test1_a.png'
        """
        try:
            from playwright.sync_api import sync_playwright

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()

                # Basic auth via Playwright context
                if auth_type == "basic" and ":" in credentials:
                    user, pwd = credentials.split(":", 1)
                    context = browser.new_context(
                        http_credentials={"username": user, "password": pwd}
                    )

                page = context.new_page()
                page.goto(url, timeout=int(self.timeout * 1000), wait_until="networkidle")
                page.screenshot(path=save_path, full_page=True)
                browser.close()

            logger.info(f"Screenshot saved: {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Screenshot failed for {url}: {e}")
            return None
