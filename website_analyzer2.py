import requests
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter
import re
import logging
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Tuple, Optional, Any
import argparse

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}


class WebsiteAnalyzer:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse HTML from the given URL."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def extract_headings(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract text from heading tags."""
        return {
            f"h{i}": [
                heading.get_text(strip=True)
                for heading in soup.find_all(f"h{i}")
                if heading.get_text(strip=True)
            ]
            for i in range(1, 7)
        }

    def extract_images_info(self, soup: BeautifulSoup, base_url: str) -> Tuple[List[Dict[str, Any]], int]:
        """Extract image details."""
        images_info = []
        image_tags = soup.find_all("img")
        for img in image_tags:
            src = img.get("src")
            alt = img.get("alt", "")
            width = img.get("width")
            height = img.get("height")

            # Resolve relative URLs
            if src and not src.startswith(("http://", "https://", "//")):
                src = urljoin(base_url, src)

            images_info.append(
                {"src": src, "alt": alt, "width": width, "height": height}
            )
        return images_info, len(image_tags)

    def extract_links_info(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """Extract link details and classify as internal/external."""
        links_info, internal_links, external_links = [], [], []
        internal_count, external_count = 0, 0

        link_tags = soup.find_all("a", href=True)
        parsed_base = urlparse(base_url)

        for a_tag in link_tags:
            href = a_tag["href"].strip()
            text = a_tag.get_text(strip=True)
            full_href = urljoin(base_url, href)
            parsed_full_href = urlparse(full_href)
            link_data = {"href": full_href, "text": text}
            links_info.append(link_data)

            if parsed_full_href.netloc == parsed_base.netloc:
                internal_links.append(link_data)
                internal_count += 1
            else:
                external_links.append(link_data)
                external_count += 1

        return {
            "total_links": len(link_tags),
            "internal_links": internal_links,
            "external_links": external_links,
            "internal_count": internal_count,
            "external_count": external_count,
        }

    def extract_meta_tags(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract meta tags for SEO/design."""
        meta_info = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name")
            property_tag = meta.get("property")
            content = meta.get("content")
            if name:
                meta_info[name] = content
            elif property_tag:
                meta_info[property_tag] = content

        title_tag = soup.find("title")
        if title_tag:
            meta_info["title"] = title_tag.get_text(strip=True)
        return meta_info

    def analyze_website(self, url: str) -> Dict[str, Any]:
        """Perform full analysis on the website."""
        logging.info(f"Analyzing: {url}")
        soup = self.fetch_html(url)
        if not soup:
            return {"error": f"Could not fetch or parse {url}"}

        analysis_results = {
            "url": url,
            "headings": self.extract_headings(soup),
            "images": {},
            "links": self.extract_links_info(soup, url),
            "meta_tags": self.extract_meta_tags(soup),
            "word_count": 0,
            "paragraph_count": 0,
            "stylesheet_count": 0,
            "script_count": 0,
        }

        images_list, total_images = self.extract_images_info(soup, url)
        analysis_results["images"] = {
            "total_images": total_images,
            "image_details": images_list,
        }

        body_tag = soup.find("body")
        if body_tag:
            text_content = body_tag.get_text(separator=" ", strip=True)
            analysis_results["word_count"] = len(text_content.split())
            analysis_results["paragraph_count"] = len(body_tag.find_all("p"))

        analysis_results["stylesheet_count"] = len(
            soup.find_all("link", rel="stylesheet")
        )
        analysis_results["script_count"] = len(
            soup.find_all("script", src=True)
        )

        logging.info("Analysis complete.")
        return analysis_results

    def print_analysis_report(self, results: Dict[str, Any]) -> None:
        """Prints formatted report of analysis."""
        if "error" in results:
            print(f"Error: {results['error']}")
            return

        print("\n" + "=" * 60)
        print(f"Website Analysis Report for: {results['url']}")
        print("=" * 60)

        print("\n--- SEO/Meta Information ---")
        for key, value in results["meta_tags"].items():
            if value:
                display_key = key.replace("og:", "Open Graph ")
                print(
                    f"  {display_key}: {value[:100]}"
                    + ("..." if len(value) > 100 else "")
                )

        print("\n--- Headings Summary ---")
        for tag, texts in results["headings"].items():
            if texts:
                print(f"  {tag.upper()} ({len(texts)} found):")
                for i, text in enumerate(texts[:5]):
                    print(
                        f"    - {text[:70]}"
                        + ("..." if len(text) > 70 else "")
                    )
                if len(texts) > 5:
                    print(f"    ... {len(texts) - 5} more")
            else:
                print(f"  {tag.upper()}: None found")

        print("\n--- Image Summary ---")
        print(f"  Total Images: {results['images']['total_images']}")
        if results["images"]["total_images"] > 0:
            alts = [
                img["alt"]
                for img in results["images"]["image_details"]
                if img["alt"]
            ]
            missing_alts = results["images"]["total_images"] - len(alts)
            print(f"  Images with Alt text: {len(alts)}")
            print(f"  Images with Missing Alt text: {missing_alts}")
            if missing_alts > 0:
                print(
                    "  (Consider adding alt text for accessibility and SEO)"
                )
            if alts:
                alt_counts = Counter(alts)
                print("  Most common Alt texts:")
                for alt, count in alt_counts.most_common(3):
                    print(f"    - '{alt[:50]}...' (x{count})")

        print("\n--- Link Summary ---")
        print(f"  Total Links: {results['links']['total_links']}")
        print(f"  Internal Links: {results['links']['internal_count']}")
        print(f"  External Links: {results['links']['external_count']}")
        if results["links"]["internal_count"] > 0:
            print("  Example Internal Links:")
            for link in results["links"]["internal_links"][:3]:
                print(
                    f"    - [{link['text'] or 'No Text'}]({link['href']})"
                )
        if results["links"]["external_count"] > 0:
            print("  Example External Links:")
            for link in results["links"]["external_links"][:3]:
                print(
                    f"    - [{link['text'] or 'No Text'}]({link['href']})"
                )

        print("\n--- Content Metrics ---")
        print(f"  Approx. Word Count: {results['word_count']}")
        print(f"  Paragraphs Found: {results['paragraph_count']}")
        print(f"  External Stylesheets: {results['stylesheet_count']}")
        print(f"  External Scripts: {results['script_count']}")

        print("\n" + "=" * 60)

    def analyze_and_report(self, url: str) -> None:
        results = self.analyze_website(url)
        self.print_analysis_report(results)


def valid_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def main():
    parser = argparse.ArgumentParser(
        description="Website Content Analyzer for Design Insights"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL of the website to analyze (e.g., https://example.com)",
    )
    args = parser.parse_args()

    analyzer = WebsiteAnalyzer()

    if args.url:
        if not valid_url(args.url):
            print("Invalid URL. Please include 'http://' or 'https://'.")
            return
        analyzer.analyze_and_report(args.url)
    else:
        print(
            "Welcome to the Website Content Analyzer for Design Insights!\n"
            "This tool helps you analyze website structures for design and SEO hints."
        )
        while True:
            target_url = input(
                "\nEnter the URL of the website to analyze (or 'quit' to exit): "
            )
            if target_url.lower() == "quit":
                break
            if not valid_url(target_url):
                print("Invalid URL. Please include 'http://' or 'https://'.")
                continue
            analyzer.analyze_and_report(target_url)
        print("\nThank you for using the Website Content Analyzer. Goodbye!")


if __name__ == "__main__":
    main()
