from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import os
import re

from agents.page_fetcher import PageFetcher
from agents.content_analyzer import ContentAnalyzer
from utils.logger import setup_logger

logger = setup_logger(__name__)


class QAComparisonAgent:
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.fetcher = PageFetcher(headless=headless, timeout=timeout)
        self.analyzer = ContentAnalyzer()

    def compare_pages(
        self,
        test_case: Dict[str, Any],
        screenshot_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare two pages and optionally take screenshots.

        Args:
            test_case: dict with URL_A, URL_B, TEST_NAME, etc.
            screenshot_dir: if provided, screenshots will be saved here.
                            Pass None to skip screenshots (default).
        """
        # Support both old (UAT_URL/PROD_URL) and new (URL_A/URL_B) headers
        url_a = test_case.get("URL_A") or test_case.get("UAT_URL")
        url_b = test_case.get("URL_B") or test_case.get("PROD_URL")

        if not url_a or not url_b:
            raise ValueError(f"Missing URL_A/URL_B (or UAT_URL/PROD_URL) in row: {test_case}")

        name = test_case.get("TEST_NAME") or url_a

        # Domains derived from each URL
        domain_a = self._extract_domain(url_a)
        domain_b = self._extract_domain(url_b)

        # Auth info (for URL_A, typically UAT)
        auth_type   = (test_case.get("AUTH_TYPE") or "").strip().lower()
        credentials = test_case.get("CREDENTIALS") or ""

        logger.info(f"Comparing: {name}")

        # ── Fetch HTML ──────────────────────────────────────────────────────
        html_a = self.fetcher.fetch_html(url_a, auth_type=auth_type, credentials=credentials)
        html_b = self.fetcher.fetch_html(url_b)

        # ── Analyze content ─────────────────────────────────────────────────
        content_a = self.analyzer.analyze(html_a, url_a)
        content_b = self.analyzer.analyze(html_b, url_b)

        # ── Text differences ────────────────────────────────────────────────
        content_issues = self._find_text_differences(
            content_a.get("text", []),
            content_b.get("text", []),
        )

        # ── Link differences ────────────────────────────────────────────────
        link_issues = self._compare_lists(
            content_a.get("links", []),
            content_b.get("links", []),
            label="link",
            domain_a=domain_a,
            domain_b=domain_b,
        )

        # ── Image differences ───────────────────────────────────────────────
        image_issues = self._compare_lists(
            content_a.get("images", []),
            content_b.get("images", []),
            label="image",
            domain_a=domain_a,
            domain_b=domain_b,
        )

        # ── Overall status ──────────────────────────────────────────────────
        status = "PASS" if not content_issues and not link_issues and not image_issues else "FAIL"

        # ── Screenshots (only if screenshot_dir is provided) ─────────────────
        screenshot_a = None
        screenshot_b = None

        if screenshot_dir:
            safe_name = re.sub(r"[^\w\-]", "_", name)[:60]  # sanitize for filename
            path_a = os.path.join(screenshot_dir, f"{safe_name}_A.png")
            path_b = os.path.join(screenshot_dir, f"{safe_name}_B.png")

            logger.info(f"Taking screenshots for: {name}")
            screenshot_a = self.fetcher.take_screenshot(
                url_a,
                save_path=path_a,
                auth_type=auth_type,
                credentials=credentials,
            )
            screenshot_b = self.fetcher.take_screenshot(url_b, save_path=path_b)

        return {
            "test_name":      name,
            "url_a":          url_a,
            "url_b":          url_b,
            "status":         status,
            "differences":    content_issues,   # legacy field
            "content_issues": content_issues,
            "link_issues":    link_issues,
            "image_issues":   image_issues,
            "screenshot_a":   screenshot_a,     # path or None
            "screenshot_b":   screenshot_b,     # path or None
        }

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url or "")
            return (parsed.netloc or "").lower()
        except Exception:
            return ""

    def _find_text_differences(
        self, texts_a: List[str], texts_b: List[str]
    ) -> List[Dict[str, Any]]:
        set_a = set(texts_a)
        set_b = set(texts_b)

        diffs: List[Dict[str, Any]] = []
        for t in sorted(set_a - set_b):
            diffs.append({"side": "A", "text": t})
        for t in sorted(set_b - set_a):
            diffs.append({"side": "B", "text": t})

        return diffs

    def _compare_lists(
        self,
        list_a: List[str],
        list_b: List[str],
        label: str,
        domain_a: str,
        domain_b: str,
    ) -> List[str]:
        issues: List[str] = []
        domain_a = (domain_a or "").lower()
        domain_b = (domain_b or "").lower()

        for value in list_a:
            if domain_b and domain_b in (value or "").lower():
                issues.append(f"{label} on A points to domain of B ({domain_b}): {value}")

        for value in list_b:
            if domain_a and domain_a in (value or "").lower():
                issues.append(f"{label} on B points to domain of A ({domain_a}): {value}")

        return issues
