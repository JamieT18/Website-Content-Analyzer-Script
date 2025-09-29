import requests
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter
import re # For regular expressions, useful for basic color/font detection later

# --- Configuration ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
HEADERS = {'User-Agent': USER_AGENT}

# --- Core Scraper Function ---
def fetch_html(url):
    """
    Fetches the HTML content of a given URL.
    Args:
        url (str): The URL of the webpage to fetch.
    Returns:
        BeautifulSoup object or None: Parsed HTML content if successful, None otherwise.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

# --- Content Extraction Functions ---

def extract_headings(soup):
    """
    Extracts all heading tags (h1, h2, h3, h4, h5, h6) and their text.
    Args:
        soup (BeautifulSoup): Parsed HTML content.
    Returns:
        dict: A dictionary where keys are heading tags (e.g., 'h1') and values are lists of their text content.
    """
    headings = {f'h{i}': [] for i in range(1, 7)}
    for i in range(1, 7):
        tag = f'h{i}'
        for heading in soup.find_all(tag):
            text = heading.get_text(strip=True)
            if text: # Only add if there's actual text
                headings[tag].append(text)
    return headings

def extract_images_info(soup, base_url):
    """
    Extracts information about images (src, alt, dimensions if available) and counts.
    Args:
        soup (BeautifulSoup): Parsed HTML content.
        base_url (str): The base URL to resolve relative image paths.
    Returns:
        tuple: (list of dict, int) - List of image info, total count of images.
    """
    images_info = []
    image_tags = soup.find_all('img')
    for img in image_tags:
        src = img.get('src')
        alt = img.get('alt', '')
        width = img.get('width')
        height = img.get('height')

        # Resolve relative URLs
        if src and not src.startswith(('http://', 'https://', '//')):
            # Simple heuristic for relative paths, can be more robust
            if base_url.endswith('/'):
                src = base_url + src
            else:
                # Handle cases like /img/path or ../img/path
                from urllib.parse import urljoin
                src = urljoin(base_url, src)

        images_info.append({
            'src': src,
            'alt': alt,
            'width': width,
            'height': height
        })
    return images_info, len(image_tags)

def extract_links_info(soup, base_url):
    """
    Extracts information about links (href, text) and counts internal/external.
    Args:
        soup (BeautifulSoup): Parsed HTML content.
        base_url (str): The base URL to determine internal vs. external links.
    Returns:
        dict: {total_links, internal_links, external_links, internal_count, external_count}
    """
    links_info = []
    internal_links = []
    external_links = []
    internal_count = 0
    external_count = 0

    link_tags = soup.find_all('a', href=True)
    for a_tag in link_tags:
        href = a_tag['href'].strip()
        text = a_tag.get_text(strip=True)

        # Resolve relative URLs for better comparison
        from urllib.parse import urljoin, urlparse
        full_href = urljoin(base_url, href)
        parsed_base = urlparse(base_url)
        parsed_full_href = urlparse(full_href)

        link_data = {'href': full_href, 'text': text}
        links_info.append(link_data)

        if parsed_full_href.netloc == parsed_base.netloc:
            internal_links.append(link_data)
            internal_count += 1
        else:
            external_links.append(link_data)
            external_count += 1

    return {
        'total_links': len(link_tags),
        'internal_links': internal_links,
        'external_links': external_links,
        'internal_count': internal_count,
        'external_count': external_count
    }

def extract_meta_tags(soup):
    """
    Extracts common meta tags useful for SEO and design context.
    Args:
        soup (BeautifulSoup): Parsed HTML content.
    Returns:
        dict: Dictionary of meta tag content.
    """
    meta_info = {}
    for meta in soup.find_all('meta'):
        name = meta.get('name')
        property_tag = meta.get('property') # For Open Graph tags like 'og:title'
        content = meta.get('content')

        if name:
            meta_info[name] = content
        elif property_tag:
            meta_info[property_tag] = content
    # Also get the title tag directly
    title_tag = soup.find('title')
    if title_tag:
        meta_info['title'] = title_tag.get_text(strip=True)
    return meta_info

# --- Main Analysis Function ---

def analyze_website(url):
    """
    Analyzes a given website for design-relevant information.
    Args:
        url (str): The URL of the website to analyze.
    Returns:
        dict: A dictionary containing all extracted and analyzed data.
    """
    print(f"\n--- Analyzing: {url} ---")
    soup = fetch_html(url)
    if not soup:
        return {"error": f"Could not fetch or parse {url}"}

    analysis_results = {
        'url': url,
        'headings': extract_headings(soup),
        'images': {}, # Placeholder, will be filled
        'links': extract_links_info(soup, url),
        'meta_tags': extract_meta_tags(soup),
        'word_count': 0, # Placeholder
        'paragraph_count': 0, # Placeholder
        'stylesheet_count': 0, # Placeholder
        'script_count': 0 # Placeholder
    }

    # Extract images info
    images_list, total_images = extract_images_info(soup, url)
    analysis_results['images'] = {
        'total_images': total_images,
        'image_details': images_list
    }

    # Basic Text Content Analysis
    body_text = soup.find('body')
    if body_text:
        text_content = body_text.get_text(separator=' ', strip=True)
        analysis_results['word_count'] = len(text_content.split())
        analysis_results['paragraph_count'] = len(body_text.find_all('p'))

    # Count stylesheets and scripts
    analysis_results['stylesheet_count'] = len(soup.find_all('link', rel='stylesheet'))
    analysis_results['script_count'] = len(soup.find_all('script', src=True)) # Only count external scripts

    print("Analysis complete.")
    return analysis_results

# --- Reporting Functions ---

def print_analysis_report(results):
    """
    Prints a formatted report of the website analysis.
    Args:
        results (dict): The analysis results dictionary.
    """
    if "error" in results:
        print(f"Error: {results['error']}")
        return

    print("\n" + "="*50)
    print(f"Website Analysis Report for: {results['url']}")
    print("="*50)

    print("\n--- SEO/Meta Information ---")
    for key, value in results['meta_tags'].items():
        if value:
            print(f"  {key.replace('og:', 'Open Graph ')}: {value[:100]}{'...' if len(value) > 100 else ''}")

    print("\n--- Headings Summary ---")
    for tag, texts in results['headings'].items():
        if texts:
            print(f"  {tag.upper()} ({len(texts)} found):")
            for i, text in enumerate(texts[:5]): # Show first 5 headings
                print(f"    - {text[:70]}{'...' if len(text) > 70 else ''}")
            if len(texts) > 5:
                print(f"    ... {len(texts) - 5} more")
        else:
            print(f"  {tag.upper()}: None found")

    print("\n--- Image Summary ---")
    print(f"  Total Images: {results['images']['total_images']}")
    if results['images']['total_images'] > 0:
        alts = [img['alt'] for img in results['images']['image_details'] if img['alt']]
        missing_alts = results['images']['total_images'] - len(alts)
        print(f"  Images with Alt text: {len(alts)}")
        print(f"  Images with Missing Alt text: {missing_alts}")
        if missing_alts > 0:
            print("  (Consider adding alt text for accessibility and SEO)")
        # Example of top used alt texts
        if alts:
            alt_counts = Counter(alts)
            print("  Most common Alt texts:")
            for alt, count in alt_counts.most_common(3):
                print(f"    - '{alt[:50]}...' (x{count})")

    print("\n--- Link Summary ---")
    print(f"  Total Links: {results['links']['total_links']}")
    print(f"  Internal Links: {results['links']['internal_count']}")
    print(f"  External Links: {results['links']['external_count']}")
    if results['links']['internal_count'] > 0:
        print("  Example Internal Links:")
        for link in results['links']['internal_links'][:3]:
            print(f"    - [{link['text'] or 'No Text'}]({link['href']})")
    if results['links']['external_count'] > 0:
        print("  Example External Links:")
        for link in results['links']['external_links'][:3]:
            print(f"    - [{link['text'] or 'No Text'}]({link['href']})")


    print("\n--- Content Metrics ---")
    print(f"  Approx. Word Count: {results['word_count']}")
    print(f"  Paragraphs Found: {results['paragraph_count']}")
    print(f"  External Stylesheets: {results['stylesheet_count']}")
    print(f"  External Scripts: {results['script_count']}")


    print("\n" + "="*50)


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Welcome to the Website Content Analyzer for Design Insights!")
    print("This tool helps you analyze website structures for design and SEO hints.")

    while True:
        target_url = input("\nEnter the URL of the website to analyze (e.g., https://example.com) or 'quit' to exit: ")
        if target_url.lower() == 'quit':
            break

        if not target_url.startswith(('http://', 'https://')):
            print("Invalid URL. Please include 'http://' or 'https://'.")
            continue

        analysis_results = analyze_website(target_url)
        print_analysis_report(analysis_results)

    print("\nThank you for using the Website Content Analyzer. Goodbye!")
