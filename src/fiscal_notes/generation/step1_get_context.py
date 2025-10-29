import os
import json
import time
import random
import fitz  # PyMuPDF
import shutil
import tempfile
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from bs4 import BeautifulSoup

def get_chrome_version():
    """
    Detect the installed Chrome version automatically.
    Returns the major version number (e.g., 141, 142).
    Works on both macOS and Linux.
    """
    import subprocess
    import re
    import platform
    
    try:
        # Determine Chrome path based on OS
        system = platform.system()
        if system == 'Darwin':  # macOS
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        elif system == 'Linux':
            chrome_path = 'google-chrome'
        else:
            print(f"Unsupported OS: {system}")
            return None
        
        # Get Chrome version
        result = subprocess.run(
            [chrome_path, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        version_string = result.stdout.strip()
        # Extract major version number (e.g., "Google Chrome 141.0.7390.123" -> 141)
        match = re.search(r'Chrome (\d+)\.', version_string)
        if match:
            version = int(match.group(1))
            print(f"✓ Detected Chrome version: {version} on {system}")
            return version
    except Exception as e:
        print(f"Could not detect Chrome version: {e}")
    
    # Default to None to let undetected-chromedriver auto-detect
    return None

def create_stealth_driver(download_dir=None, port=None):
    """
    Create a more stealth-oriented Chrome driver to bypass Cloudflare bot detection.
    Automatically detects and uses the correct Chrome version.
    """
    # Auto-detect Chrome version
    chrome_version = get_chrome_version()
    
    options = uc.ChromeOptions()
    
    # Basic stealth options
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins-discovery')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--no-first-run')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-features=VizDisplayCompositor')
    
    # Headless mode with new implementation
    options.add_argument('--headless=new')
    
    # Set a realistic user agent (dynamically set version if detected)
    if chrome_version:
        options.add_argument(f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36')
    else:
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36')
    
    # Window size to appear more realistic
    options.add_argument('--window-size=1920,1080')
    
    # Download preferences if download_dir is provided
    if download_dir:
        options.add_experimental_option("prefs", {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
    
    # Additional experimental options to avoid detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Add unique port if specified to avoid conflicts
    if port:
        options.add_argument(f'--remote-debugging-port={port}')
    
    try:
        # Create driver with auto-detected version and enhanced stealth
        if chrome_version:
            print(f"Creating ChromeDriver with version_main={chrome_version}")
            driver = uc.Chrome(
                options=options, 
                version_main=chrome_version, 
                port=port if port else 0,
                use_subprocess=True,  # Better stealth
                driver_executable_path=None  # Let UC handle it
            )
        else:
            print("Creating ChromeDriver with auto-detection")
            driver = uc.Chrome(
                options=options, 
                port=port if port else 0,
                use_subprocess=True
            )
        
        # Enhanced stealth scripts
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": driver.execute_script("return navigator.userAgent").replace('HeadlessChrome', 'Chrome')
        })
        
        # Remove webdriver traces
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        return driver
    except Exception as e:
        print(f"Error creating stealth driver with full options: {e}")
        if "version" in str(e).lower() or "chrome" in str(e).lower():
            print("Chrome/ChromeDriver version mismatch detected. Trying fallback options...")
        
        # Fallback to basic driver with minimal options
        basic_options = uc.ChromeOptions()
        basic_options.add_argument('--headless=new')
        basic_options.add_argument('--no-sandbox')
        basic_options.add_argument('--disable-dev-shm-usage')
        
        if download_dir:
            basic_options.add_experimental_option("prefs", {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True
            })
        
        try:
            if chrome_version:
                driver = uc.Chrome(options=basic_options, version_main=chrome_version, port=port if port else 0, use_subprocess=True)
            else:
                driver = uc.Chrome(options=basic_options, port=port if port else 0, use_subprocess=True)
            
            # Apply stealth scripts
            try:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": driver.execute_script("return navigator.userAgent").replace('HeadlessChrome', 'Chrome')
                })
            except:
                pass
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e2:
            print(f"Error creating basic driver: {e2}")
            # Ultimate fallback - let undetected-chromedriver fully auto-detect
            try:
                print("Trying ultimate fallback with auto-detection...")
                driver = uc.Chrome(port=port if port else 0)
                return driver
            except Exception as e3:
                print(f"All driver creation attempts failed: {e3}")
                raise

def wait_with_random_delay(min_seconds=2, max_seconds=5):
    """Wait with a random delay to appear more human-like."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def retry_with_backoff(func, max_retries=3, base_delay=2):
    """Retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)

def table_html_to_numbered_list(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="MainContent_GridViewStatus")
    if not table:
        return []

    numbered_list = []
    rows = table.find_all("tr")[1:]  # skip header row

    for i, row in enumerate(rows, start=1):
        cells = row.find_all("td")
        if len(cells) >= 3:
            date = cells[0].get_text(strip=True)
            chamber = cells[1].get_text(strip=True)
            status = cells[2].get_text(strip=True)
            numbered_list.append(f"{i}. {date} | {chamber} | {status}")

    return numbered_list

from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_measure_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    # 1️⃣ Links inside div.noprint
    noprint_div = soup.find("div", class_="noprint")
    if noprint_div:
        for a in noprint_div.find_all("a", href=True):
            links.append(urljoin(base_url, a["href"]))

    # 2️⃣ Links inside subsequent divs with class starting with 'measure-status card shadow'
    measure_divs = soup.find_all("div", class_="measure-status card shadow")
    # Include possible variation with "text-center"
    measure_divs += soup.find_all("div", class_="measure-status card shadow text-center")

    # Find the "Committee Reports" card
    committee_reports_div = soup.find("h2", string="Committee Reports").find_parent("div", class_="measure-status")

    # Extract all <a> links that are NOT the PDF ones (only the text links)
    links = committee_reports_div.select("a[id^='MainContent_RepeaterCommRpt_CategoryLink']")

    names = [link.get_text(strip=True) for link in links]


    for div in measure_divs:
        for a in div.find_all("a", href=True):
            links.append(urljoin(base_url, a["href"]))

    # remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            unique_links.append(link)
            seen.add(link)

    return unique_links, names

def extract_measure_documents_with_links(html, base_url):
    """
    Extract documents along with their URLs.
    Returns a list of dicts: [{"name": "HB400_HD1", "url": "..."}]
    """
    soup = BeautifulSoup(html, "html.parser")
    documents = []

    # 1️⃣ Documents inside div.noprint
    noprint_div = soup.find("div", class_="noprint")
    if noprint_div:
        for a in noprint_div.find_all("a", href=True):
            name = a.get_text(strip=True)
            url = urljoin(base_url, a["href"])
            if name:
                documents.append({"name": name, "url": url})

    # 2️⃣ Documents inside divs with class starting with 'measure-status card shadow'
    measure_divs = soup.find_all("div", class_="measure-status card shadow")
    # measure_divs += soup.find_all("div", class_="measure-status card shadow text-center")
    for div in measure_divs:
        for a in div.find_all("a", href=True):
            name = a.get_text(strip=True)
            url = urljoin(base_url, a["href"])
            if name:
                # Avoid duplicates
                if not any(d["name"] == name for d in documents):
                    documents.append({"name": name, "url": url})

    return documents


def clean_html_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def extract_pdf_text_from_file(file_path):
    try:
        doc = fitz.open(file_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        return f"[ERROR extracting PDF text: {e}]"

def create_timeline_data(status_rows):
    """
    Convert status rows into timeline data format.
    Each status row should be in format: "1. date | chamber | status"
    Returns a list of timeline objects with date, text, and empty documents array.
    """
    timeline_data = []
    
    for row in status_rows:
        if not row.strip():
            continue
            
        # Parse the format: "1. date | chamber | status"
        parts = row.split(" | ")
        if len(parts) >= 3:
            # Remove the number prefix (e.g., "1. ")
            date_part = parts[0].split(". ", 1)[1] if ". " in parts[0] else parts[0]
            chamber = parts[1]
            status = parts[2]
            
            # Create timeline entry
            timeline_entry = {
                "date": date_part.strip(),
                "text": f"{chamber}: {status}".strip(),
                "documents": []
            }
            timeline_data.append(timeline_entry)
    
    return timeline_data

def fetch_documents(measure_url: str) -> str:
    parsed = urlparse(measure_url)
    params = parse_qs(parsed.query)
    billtype = params.get("billtype", ["UNKNOWN"])[0]
    billnumber = params.get("billnumber", ["UNKNOWN"])[0]
    year = params.get("year", ["UNKNOWN"])[0]

    # Create output directory alongside this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, f"{billtype}_{billnumber}_{year}")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = os.path.join(output_dir, f"{billtype}_{billnumber}_{year}.json")

    # Setup download directory for PDFs
    download_dir = tempfile.mkdtemp()

    # Generate unique port for this job to avoid conflicts
    import hashlib
    job_hash = hashlib.md5(f"{billtype}_{billnumber}_{year}".encode()).hexdigest()[:8]
    unique_port = 9222 + int(job_hash, 16) % 1000  # Port range 9222-10222

    # Use the new stealth driver with unique port
    driver = create_stealth_driver(download_dir, port=unique_port)

    def load_page_with_retry():
        driver.get(measure_url)
        wait_with_random_delay(3, 6)  # Wait longer to bypass Cloudflare
        
        # Check if we hit Cloudflare protection
        page_source = driver.page_source.lower()
        if "cloudflare" in page_source or "attention required" in page_source:
            raise WebDriverException("Cloudflare protection detected")
        
        print(f"Page loaded successfully. First 500 chars: {driver.page_source[:500]}")
        return True

    try:
        # Try to load the page with retry logic
        retry_with_backoff(load_page_with_retry, max_retries=3, base_delay=5)
        
        # Collect all links inside main-content
        main = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "main-content"))
        )
        # main = driver.find_element(By.ID, "main-content")
        a_tags = main.find_elements(By.XPATH, ".//a[@href]")
        base_url = measure_url
        raw_links = [urljoin(base_url, a.get_attribute("href")) for a in a_tags]
        _ = [u for u in raw_links if u.lower().endswith((".htm", ".pdf"))]

        # Prefer .htm if both .htm and .pdf exist for same base (currently disabled)
        unique_docs = {}

        results = []
        for doc_url in unique_docs.values():
            if doc_url.lower().endswith(".htm"):
                driver.get(doc_url)
                wait_with_random_delay(2, 4)
                html = driver.page_source
                text = clean_html_text(html)
                results.append({"url": doc_url, "text": text})
            elif doc_url.lower().endswith(".pdf"):
                # Remove old files first
                for f in os.listdir(download_dir):
                    os.remove(os.path.join(download_dir, f))
                # Click the PDF link
                driver.get(measure_url)  # Reload base page to stay consistent
                wait_with_random_delay(2, 4)
                link_el = driver.find_element(By.XPATH, f'//a[@href="{urlparse(doc_url).path}"]')
                link_el.click()
                wait_with_random_delay(3, 6)  # Wait for download

                # Find the downloaded PDF file
                downloaded_pdf = next((os.path.join(download_dir, f)
                                       for f in os.listdir(download_dir)
                                       if f.lower().endswith(".pdf")), None)
                if downloaded_pdf:
                    text = extract_pdf_text_from_file(downloaded_pdf)
                    results.append({"url": doc_url, "text": text})
                else:
                    results.append({"url": doc_url, "text": "[ERROR: PDF not downloaded]"})

        # Process starting page first
        driver.get(measure_url)
        wait_with_random_delay(1, 2)
        html = driver.page_source
        text = table_html_to_numbered_list(html)
        links, names = extract_measure_links(html, measure_url)
        documents = extract_measure_documents_with_links(html, measure_url)

        results.append({"url": measure_url, "text": text, "links": links, "documents": documents, "comittee_reports": names})

        # Clean links structure if present
        for item in results:
            if "links" in item and isinstance(item["links"], list):
                cleaned_links = []
                for link in item["links"]:
                    if hasattr(link, "get"):
                        cleaned_links.append({
                            "name": link.get_text(strip=True),
                            "url": link["href"]
                        })
                    else:
                        cleaned_links.append(link)
                item["links"] = cleaned_links

        # Save results
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Create and save timeline data
        timeline_data = create_timeline_data(text)
        timeline_filename = os.path.join(output_dir, f"{billtype}_{billnumber}_{year}_timeline.json")
        with open(timeline_filename, "w", encoding="utf-8") as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Timeline data saved to {timeline_filename}")

        return output_filename
    finally:
        try:
            driver.quit()
        finally:
            shutil.rmtree(download_dir)


__all__ = ["fetch_documents", "create_timeline_data"]
