from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import os
import re
import ssl
import socket
import requests

from agents.page_fetcher import PageFetcher
from agents.content_analyzer import ContentAnalyzer
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Global environment keywords 
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

        # ── Link Audit ──────────────────────────────────────────────────────
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

        # ── Page Health (Title + Status Code + SSL) ─────────────────────────
        page_health = self._check_page_health(url_a, url_b)

        # ── Overall status ──────────────────────────────────────────────────
        health_issues = (
            page_health.get("title_issues", []) +
            page_health.get("status_issues", []) +
            page_health.get("ssl_issues", [])
        )
        status = "PASS" if not content_issues and not link_issues and not image_issues and not health_issues else "FAIL"

        # ── Screenshots ─────────────────────────────────────────────────────
        screenshot_a = screenshot_b = None
        if screenshot_dir:
            safe_name    = re.sub(r"[^\w\-]", "_", name)[:60]
            path_a       = os.path.join(screenshot_dir, f"{safe_name}_A.png")
            path_b       = os.path.join(screenshot_dir, f"{safe_name}_B.png")
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
            "page_health":    page_health,
            "screenshot_a":   screenshot_a,
            "screenshot_b":   screenshot_b,
        }

    # ════════════════════════════════════════════════════════════════════════
    # PAGE HEALTH CHECKS
    # ════════════════════════════════════════════════════════════════════════

    def _check_page_health(self, url_a: str, url_b: str) -> Dict[str, Any]:
        """Run Title, Status Code and SSL checks on both URLs."""
        return {
            "title_a":       self._get_page_title(url_a),
            "title_b":       self._get_page_title(url_b),
            "title_issues":  self._check_titles(url_a, url_b),
            "status_a":      self._get_status_code(url_a),
            "status_b":      self._get_status_code(url_b),
            "status_issues": self._check_status_codes(url_a, url_b),
            "ssl_a":         self._check_ssl(url_a),
            "ssl_b":         self._check_ssl(url_b),
            "ssl_issues":    self._check_ssl_issues(url_a, url_b),
        }

    # ── Page Title ───────────────────────────────────────────────────────────

    def _get_page_title(self, url: str) -> str:
        """Extract page title from URL."""
        try:
            resp  = requests.get(url, timeout=10, headers={"User-Agent": "QAAgent/1.0"})
            match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else "No title found"
        except Exception as e:
            logger.warning(f"Could not fetch title for {url}: {e}")
            return "Error fetching title"

    def _check_titles(self, url_a: str, url_b: str) -> List[str]:
        """Compare page titles between URL A and URL B."""
        issues  = []
        title_a = self._get_page_title(url_a)
        title_b = self._get_page_title(url_b)

        if title_a == "Error fetching title":
            issues.append(f"[TITLE] Could not fetch title for URL A")
        if title_b == "Error fetching title":
            issues.append(f"[TITLE] Could not fetch title for URL B")

        if title_a not in ("Error fetching title", "No title found") and \
           title_b not in ("Error fetching title", "No title found"):
            if title_a != title_b:
                issues.append(f"[TITLE MISMATCH] URL A: '{title_a}' vs URL B: '{title_b}'")

        if title_b == "No title found":
            issues.append(f"[TITLE] URL B is missing a page title — bad for SEO")

        return issues

    # ── Status Code ──────────────────────────────────────────────────────────

    def _get_status_code(self, url: str) -> int:
        """Get HTTP status code for a URL."""
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True,
                                 headers={"User-Agent": "QAAgent/1.0"})
            return resp.status_code
        except Exception as e:
            logger.warning(f"Could not get status for {url}: {e}")
            return 0

    def _check_status_codes(self, url_a: str, url_b: str) -> List[str]:
        """Check HTTP status codes for both URLs."""
        issues   = []
        status_a = self._get_status_code(url_a)
        status_b = self._get_status_code(url_b)

        for label, status, url in [("URL A", status_a, url_a), ("URL B", status_b, url_b)]:
            if status == 0:
                issues.append(f"[STATUS] {label} — Could not connect to {url}")
            elif status == 200:
                pass  # all good
            elif status in (301, 302):
                issues.append(f"[STATUS] {label} — Redirecting ({status}): {url}")
            elif status == 403:
                issues.append(f"[STATUS] {label} — Access forbidden (403): {url}")
            elif status == 404:
                issues.append(f"[STATUS] {label} — Page not found (404): {url}")
            elif status == 500:
                issues.append(f"[STATUS] {label} — Server error (500): {url}")
            elif status >= 400:
                issues.append(f"[STATUS] {label} — Client error ({status}): {url}")
            elif status >= 500:
                issues.append(f"[STATUS] {label} — Server error ({status}): {url}")

        return issues

    # ── SSL Certificate ──────────────────────────────────────────────────────

    def _check_ssl(self, url: str) -> Dict[str, Any]:
        """Check SSL certificate validity and expiry for a URL."""
        import datetime
        parsed = urlparse(url)

        if parsed.scheme != "https":
            return {"valid": False, "reason": "Not using HTTPS", "expires": None}

        hostname = parsed.hostname
        port     = parsed.port or 443

        try:
            ctx  = ssl.create_default_context()
            conn = ctx.wrap_socket(
                socket.create_connection((hostname, port), timeout=10),
                server_hostname=hostname
            )
            cert        = conn.getpeercert()
            conn.close()

            expire_str  = cert.get("notAfter", "")
            expire_date = datetime.datetime.strptime(expire_str, "%b %d %H:%M:%S %Y %Z")
            days_left   = (expire_date - datetime.datetime.utcnow()).days

            return {
                "valid":    True,
                "expires":  expire_date.strftime("%Y-%m-%d"),
                "days_left": days_left,
                "reason":   "Valid"
            }

        except ssl.SSLCertVerificationError as e:
            return {"valid": False, "reason": f"SSL verification failed: {e}", "expires": None}
        except Exception as e:
            return {"valid": False, "reason": f"SSL check failed: {e}", "expires": None}

    def _check_ssl_issues(self, url_a: str, url_b: str) -> List[str]:
        """Report SSL issues for both URLs."""
        issues = []

        for label, url in [("URL A", url_a), ("URL B", url_b)]:
            result = self._check_ssl(url)

            if not result["valid"]:
                issues.append(f"[SSL] {label} — {result['reason']}: {url}")
            elif result.get("days_left") is not None:
                days = result["days_left"]
                if days <= 0:
                    issues.append(f"[SSL] {label} — Certificate EXPIRED: {url}")
                elif days <= 7:
                    issues.append(f"[SSL] {label} — Certificate expires in {days} day(s) ⚠️ CRITICAL: {url}")
                elif days <= 30:
                    issues.append(f"[SSL] {label} — Certificate expires in {days} day(s) ⚠️ WARNING: {url}")

        return issues

    # ════════════════════════════════════════════════════════════════════════
    # LINK AUDIT
    # ════════════════════════════════════════════════════════════════════════

    def _check_link_integrity(
        self,
        links_a: List[str],
        links_b: List[str],
        domain_a: str,
        domain_b: str,
    ) -> List[str]:
        issues = []
        set_a  = set(links_a)
        set_b  = set(links_b)

        issues += self._cross_domain_check(links_a, links_b, domain_a, domain_b)
        issues += self._env_keyword_check(links_b, page_label="PROD (URL B)")

        for link in sorted(set_a - set_b):
            issues.append(f"[MISSING ON B] Link exists on URL A but not on URL B: {link}")
        for link in sorted(set_b - set_a):
            issues.append(f"[EXTRA ON B] Link exists on URL B but not on URL A: {link}")

        issues += self._check_broken_links(set_a | set_b)

        return issues