from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import os
import re
import requests

from agents.page_fetcher import PageFetcher
from agents.content_analyzer import ContentAnalyzer
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ── Global environment keywords to detect non-prod links in prod ────────────
ENV_KEYWORDS = ["uat", "staging", "stage", "dev", "development", "test",
                "qa", "sandbox", "preprod", "pre-prod", "sit", "ht", "int"]


class QAComparisonAgent:
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.fetcher = PageFetcher(headless=headless, timeout=timeout)
        self.analyzer = ContentAnalyzer()

    def compare_pages(
        self,
        test_case: Dict[str, Any],
        screenshot_dir: Optional[str] = None,
    ) -> Dict[str, Any]:

        url_a = test_case.get("URL_A") or test_case.get("UAT_URL")
        url_b = test_case.get("URL_B") or test_case.get("PROD_URL")

        if not url_a or not url_b:
            raise ValueError(f"Missing URL_A/URL_B in row: {test_case}")

        name     = test_case.get("TEST_NAME") or url_a
        domain_a = self._extract_domain(url_a)
        domain_b = self._extract_domain(url_b)

        auth_type   = (test_case.get("AUTH_TYPE") or "").strip().lower()
        credentials = test_case.get("CREDENTIALS") or ""

        logger.info(f"Comparing: {name}")

        # ── Fetch HTML ──────────────────────────────────────────────────────
        html_a = self.fetcher.fetch_html(url_a, auth_type=auth_type, credentials=credentials)
        html_b = self.fetcher.fetch_html(url_b)

        # ── Analyze content ─────────────────────────────────────────────────
        content_a = self.analyzer.analyze(html_a, url_a)
        content_b = self.analyzer.analyze(html_b, url_b)

        links_a  = content_a.get("links", [])
        links_b  = content_b.get("links", [])
        images_a = content_a.get("images", [])
        images_b = content_b.get("images", [])

        # ── Text differences ────────────────────────────────────────────────
        content_issues = self._find_text_differences(
            content_a.get("text", []),
            content_b.get("text", []),
        )

        # ── Link integrity ──────────────────────────────────────────────────
        link_issues = self._check_link_integrity(
            links_a, links_b,
            domain_a=domain_a,
            domain_b=domain_b,
        )

        # ── Image differences ───────────────────────────────────────────────
        image_issues = self._compare_lists(
            images_a, images_b,
            label="image",
            domain_a=domain_a,
            domain_b=domain_b,
        )

        status = "PASS" if not content_issues and not link_issues and not image_issues else "FAIL"

        # ── Screenshots ─────────────────────────────────────────────────────
        screenshot_a = screenshot_b = None
        if screenshot_dir:
            safe_name  = re.sub(r"[^\w\-]", "_", name)[:60]
            path_a     = os.path.join(screenshot_dir, f"{safe_name}_A.png")
            path_b     = os.path.join(screenshot_dir, f"{safe_name}_B.png")
            screenshot_a = self.fetcher.take_screenshot(url_a, save_path=path_a, auth_type=auth_type, credentials=credentials)
            screenshot_b = self.fetcher.take_screenshot(url_b, save_path=path_b)

        return {
            "test_name":      name,
            "url_a":          url_a,
            "url_b":          url_b,
            "status":         status,
            "differences":    content_issues,
            "content_issues": content_issues,
            "link_issues":    link_issues,
            "image_issues":   image_issues,
            "screenshot_a":   screenshot_a,
            "screenshot_b":   screenshot_b,
        }

    # ════════════════════════════════════════════════════════════════════════
    # LINK INTEGRITY  (fully rewritten)
    # ════════════════════════════════════════════════════════════════════════

    def _check_link_integrity(
        self,
        links_a: List[str],
        links_b: List[str],
        domain_a: str,
        domain_b: str,
    ) -> List[str]:
        issues: List[str] = []

        set_a = set(links_a)
        set_b = set(links_b)

        # 1️⃣  Cross-domain check (global, works for any site)
        #     If a link on the PROD page (B) contains domain of UAT (A) → wrong!
        issues += self._cross_domain_check(links_a, links_b, domain_a, domain_b)

        # 2️⃣  UAT/staging/dev keywords found in PROD links (global)
        issues += self._env_keyword_check(links_b, page_label="PROD (URL B)")

        # 3️⃣  Missing links — present on A but not on B
        for link in sorted(set_a - set_b):
            issues.append(f"[MISSING ON B] Link exists on URL A but not on URL B: {link}")

        # 4️⃣  Extra links — present on B but not on A
        for link in sorted(set_b - set_a):
            issues.append(f"[EXTRA ON B] Link exists on URL B but not on URL A: {link}")

        # 5️⃣  Broken links check (checks both pages)
        issues += self._check_broken_links(set_a, page_label="URL A")
        issues += self._check_broken_links(set_b, page_label="URL B")

        return issues

    def _cross_domain_check(
        self,
        links_a: List[str],
        links_b: List[str],
        domain_a: str,
        domain_b: str,
    ) -> List[str]:
        """Flag links that point to the wrong environment's domain."""
        issues = []
        domain_a = (domain_a or "").lower()
        domain_b = (domain_b or "").lower()

        for link in links_a:
            if domain_b and domain_b in (link or "").lower():
                issues.append(f"[CROSS-DOMAIN] URL A contains a link pointing to URL B's domain: {link}")

        for link in links_b:
            if domain_a and domain_a in (link or "").lower():
                issues.append(f"[CROSS-DOMAIN] URL B (PROD) contains a link pointing to URL A's domain ({domain_a}): {link}")

        return issues

    def _env_keyword_check(self, links: List[str], page_label: str) -> List[str]:
        """
        Globally detect environment-specific keywords in any link.
        Works for ANY site — not hardcoded to a specific domain.
        Flags links like: uat.anything.com, staging-api.example.com, dev.mysite.io
        """
        issues = []
        for link in links:
            parsed = urlparse(link or "")
            host   = (parsed.netloc or "").lower()
            # Check each part of the hostname split by dots and hyphens
            parts  = re.split(r"[\.\-]", host)
            for keyword in ENV_KEYWORDS:
                if keyword in parts:
                    issues.append(
                        f"[ENV LEAK] {page_label} contains a non-production link "
                        f"('{keyword}' detected in hostname): {link}"
                    )
                    break  # one warning per link is enough

        return issues

    def _check_broken_links(self, links: set, page_label: str) -> List[str]:
        """Check each link for HTTP errors (404, 500, etc.)."""
        issues  = []
        headers = {"User-Agent": "Mozilla/5.0 QAComparisonAgent/1.0"}

        for link in links:
            if not link or not link.startswith("http"):
                continue
            try:
                resp = requests.head(link, timeout=8, allow_redirects=True, headers=headers)
                if resp.status_code >= 400:
                    issues.append(
                        f"[BROKEN LINK] {page_label} — HTTP {resp.status_code}: {link}"
                    )
            except requests.exceptions.Timeout:
                issues.append(f"[BROKEN LINK] {page_label} — Timed out: {link}")
            except requests.exceptions.ConnectionError:
                issues.append(f"[BROKEN LINK] {page_label} — Connection failed: {link}")
            except Exception as e:
                logger.warning(f"Could not check link {link}: {e}")

        return issues

    # ════════════════════════════════════════════════════════════════════════
    # OTHER HELPERS
    # ════════════════════════════════════════════════════════════════════════

    def _find_text_differences(
        self, texts_a: List[str], texts_b: List[str]
    ) -> List[Dict[str, Any]]:
        set_a = set(texts_a)
        set_b = set(texts_b)
        diffs = []
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
        """Used for image comparison — cross-domain check only."""
        issues  = []
        domain_a = (domain_a or "").lower()
        domain_b = (domain_b or "").lower()

        for value in list_a:
            if domain_b and domain_b in (value or "").lower():
                issues.append(f"{label} on A points to domain of B ({domain_b}): {value}")
        for value in list_b:
            if domain_a and domain_a in (value or "").lower():
                issues.append(f"{label} on B points to domain of A ({domain_a}): {value}")

        return issues

    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url or "")
            return (parsed.netloc or "").lower()
        except Exception:
            return ""