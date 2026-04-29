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
        Falls back to Playwright if requests fails or returns empty.
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

    def fetch_html_with_js(self, url: str, auth_type: Optional[str] = None, credentials: str = "") -> str:
        """Fetch JS-rendered HTML using Selenium."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.support.ui import WebDriverWait

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.binary_location = "/usr/bin/chromium"

            service = Service("/usr/bin/chromedriver")
            driver  = webdriver.Chrome(service=service, options=options)

            driver.get(url)
            # Wait for page to fully load
            import time
            time.sleep(3)
            html = driver.page_source
            driver.quit()
            return html

        except Exception as e:
            logger.warning(f"Selenium JS fetch failed for {url}: {e}")
            # Fallback to requests
            return self.fetch_html(url, auth_type=auth_type, credentials=credentials)

    def take_screenshot(
        self,
        url: str,
        save_path: str,
        auth_type: Optional[str] = None,
        credentials: str = "",
    ) -> Optional[str]:
        """
        Take a full-page screenshot of the URL using Playwright.
        """
        try:
            from playwright.sync_api import sync_playwright

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)

                context_options = {}
                if auth_type == "basic" and ":" in credentials:
                    user, pwd = credentials.split(":", 1)
                    context_options["http_credentials"] = {"username": user, "password": pwd}

                context = browser.new_context(**context_options)
                page    = context.new_page()
                page.goto(url, timeout=int(self.timeout * 1000), wait_until="networkidle")
                page.screenshot(path=save_path, full_page=True)
                browser.close()

            logger.info(f"Screenshot saved: {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Screenshot failed for {url}: {e}")
            return None