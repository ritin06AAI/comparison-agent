from bs4 import BeautifulSoup
from typing import Dict, Any, List

class ContentAnalyzer:
    def analyze(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        # Remove global chrome: header, nav, footer
        self._remove_chrome(soup)

        return {
            "url": url,
            "text": self._extract_text(soup),
            "links": self._extract_links(soup),
            "images": self._extract_images(soup),
        }

    def _remove_chrome(self, soup: BeautifulSoup) -> None:
        """
        Remove navigation / header / footer blocks so we don't flag
        differences in global site chrome.

        You can extend this with more selectors if needed.
        """

        # Remove semantic tags
        for tag_name in ["header", "nav", "footer"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Optional: remove known classes/ids if your site uses them
        nav_classes = ["site-header", "global-nav", "main-nav", "site-footer", "global-footer"]
        for cls in nav_classes:
            for tag in soup.find_all(class_=cls):
                tag.decompose()

        # Optional: remove elements by id
        nav_ids = ["header", "navbar", "site-header", "site-footer", "footer"]
        for id_ in nav_ids:
            tag = soup.find(id=id_)
            if tag:
                tag.decompose()

    def _extract_text(self, soup: BeautifulSoup) -> List[str]:
        texts = []
        for elem in soup.find_all(["h1", "h2", "h3", "p", "span", "button", "a"]):
            t = elem.get_text(strip=True)
            if t:
                texts.append(t)
        return texts

    def _extract_links(self, soup: BeautifulSoup) -> List[str]:
        hrefs = []
        for a in soup.find_all("a", href=True):
            hrefs.append(a.get("href").strip())
        return hrefs

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        srcs = []
        for img in soup.find_all("img", src=True):
            srcs.append(img.get("src").strip())
        return srcs
