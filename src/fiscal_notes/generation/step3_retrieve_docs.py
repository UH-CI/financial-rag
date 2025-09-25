import os
import json
import time
import random
import fitz  # PyMuPDF
import shutil
import tempfile
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

def create_stealth_driver(download_dir=None):
    """
    Create a more stealth-oriented Chrome driver to bypass Cloudflare bot detection.
    """
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
    
    # Set a realistic user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
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
    
    try:
        # Create driver with version_main to avoid compatibility issues
        driver = uc.Chrome(options=options, version_main=None)
        
        # Execute script to remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"Error creating stealth driver with full options: {e}")
        # Fallback to basic driver with minimal options
        basic_options = uc.ChromeOptions()
        basic_options.add_argument('--headless=new')
        basic_options.add_argument('--no-sandbox')
        basic_options.add_argument('--disable-dev-shm-usage')
        basic_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        if download_dir:
            basic_options.add_experimental_option("prefs", {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True
            })
        
        try:
            driver = uc.Chrome(options=basic_options, version_main=None)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e2:
            print(f"Error creating basic driver: {e2}")
            # Ultimate fallback
            return uc.Chrome()

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

def parse_web_document_selenium(url, output_dir):
    """
    Fetch a single HTML or PDF page using Selenium (undetected) to bypass Cloudflare,
    extract text, and save it as a .txt file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Derive a safe filename from URL
    path = urlparse(url).path
    filename_base = os.path.basename(path) or "document"
    txt_filename = os.path.join(output_dir, f"{filename_base}.txt")

    # Setup temp download directory for PDFs
    download_dir = tempfile.mkdtemp()

    # Use the new stealth driver
    driver = create_stealth_driver(download_dir)

    def clean_html_text(html):
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def extract_pdf_text(file_path):
        try:
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except Exception as e:
            return f"[ERROR extracting PDF text: {e}]"

    def load_page_with_retry():
        driver.get(url)
        wait_with_random_delay(3, 6)  # Wait longer to bypass Cloudflare
        
        # Check if we hit Cloudflare protection
        page_source = driver.page_source.lower()
        if "cloudflare" in page_source or "attention required" in page_source:
            raise WebDriverException("Cloudflare protection detected")
        
        print(f"Page loaded successfully for: {url}")
        return True

    try:
        # Try to load the page with retry logic
        retry_with_backoff(load_page_with_retry, max_retries=3, base_delay=5)

        if url.lower().endswith((".htm", ".html")):
            html = driver.page_source
            text = clean_html_text(html)

        if url.lower().endswith(".pdf"):
            # Navigate directly to the PDF URL
            driver.get(url)
            wait_with_random_delay(3, 6)  # give time for PDF to download

            # Find the downloaded PDF
            downloaded_pdf = next((os.path.join(download_dir, f)
                                for f in os.listdir(download_dir)
                                if f.lower().endswith(".pdf")), None)
            if downloaded_pdf:
                text = extract_pdf_text(downloaded_pdf)
            else:
                return f"❌ PDF not downloaded: {url}"


        # Save text
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(text)

        return f"✅ Saved text: {txt_filename}"

    except Exception as e:
        return f"❌ Failed to parse {url}: {e}"

    finally:
        driver.quit()
        shutil.rmtree(download_dir)


def retrieve_documents(chronological_json_path: str) -> str:
    """
    Takes a chronological JSON file path and retrieves all documents,
    saving them as text files in the same bill directory.
    Returns the path to the documents directory.
    """
    # Load the chronological documents
    with open(chronological_json_path, 'r', encoding='utf-8') as f:
        documents_chronological = json.load(f)
    
    # Create documents directory in the same folder as the JSON
    base_dir = os.path.dirname(chronological_json_path)
    documents_dir = os.path.join(base_dir, "documents")
    os.makedirs(documents_dir, exist_ok=True)
    
    # Retrieve each document
    results = []
    for i, doc in enumerate(documents_chronological):
        print(f"Processing document {i+1}/{len(documents_chronological)}: {doc.get('name', 'Unknown')}")
        result = parse_web_document_selenium(doc['url'], documents_dir)
        results.append({
            "document": doc,
            "result": result
        })
        print(result)
        
        # Add random delay between documents to appear more human-like
        if i < len(documents_chronological) - 1:  # Don't wait after the last document
            wait_with_random_delay(1, 3)
    
    # Save retrieval results log
    log_file = os.path.join(base_dir, "retrieval_log.json")
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ All documents retrieved and saved to: {documents_dir}")
    print(f"📋 Retrieval log saved to: {log_file}")
    
    return documents_dir


__all__ = ["retrieve_documents"]
