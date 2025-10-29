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

def parse_web_document_selenium_with_driver(url, output_dir, driver, download_dir):
    """
    Fetch a single HTML or PDF page using an existing Selenium driver,
    extract text, and save it as a .txt file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Derive a safe filename from URL
    path = urlparse(url).path
    filename_base = os.path.basename(path) or "document"
    txt_filename = os.path.join(output_dir, f"{filename_base}.txt")

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
        # Reduced delay since we're reusing the driver
        wait_with_random_delay(1, 2)  # Reduced from 3-6 to 1-2 seconds
        
        # Check if we hit Cloudflare protection
        page_source = driver.page_source.lower()
        if "cloudflare" in page_source or "attention required" in page_source:
            raise WebDriverException("Cloudflare protection detected")
        
        print(f"Page loaded successfully for: {url}")
        return True

    try:
        # Try to load the page with retry logic
        retry_with_backoff(load_page_with_retry, max_retries=3, base_delay=2)  # Reduced base delay

        if url.lower().endswith((".htm", ".html")):
            html = driver.page_source
            text = clean_html_text(html)

        if url.lower().endswith(".pdf"):
            # Clear any existing PDF files first
            for f in os.listdir(download_dir):
                if f.lower().endswith(".pdf"):
                    os.remove(os.path.join(download_dir, f))
                    
            # Navigate directly to the PDF URL
            driver.get(url)
            wait_with_random_delay(2, 4)  # Reduced delay for PDF downloads

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


def parse_web_document_selenium(url, output_dir):
    """
    Legacy function that creates a new driver for each document (kept for compatibility).
    Use parse_web_document_selenium_with_driver for better performance.
    """
    # Setup temp download directory for PDFs
    download_dir = tempfile.mkdtemp()
    
    try:
        # Generate unique port for this document
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        unique_port = 9222 + int(url_hash, 16) % 1000
        
        # Use the new stealth driver
        driver = create_stealth_driver(download_dir, port=unique_port)
        result = parse_web_document_selenium_with_driver(url, output_dir, driver, download_dir)
        return result
    finally:
        if 'driver' in locals():
            driver.quit()
        shutil.rmtree(download_dir)


def retrieve_documents(chronological_json_path: str) -> str:
    """
    Takes a chronological JSON file path and retrieves all documents,
    saving them as text files in the same bill directory.
    Uses a single Chrome instance for all documents to improve performance.
    Returns the path to the documents directory.
    """
    # Load the chronological documents
    with open(chronological_json_path, 'r', encoding='utf-8') as f:
        documents_chronological = json.load(f)
    
    # Create documents directory in the same folder as the JSON
    base_dir = os.path.dirname(chronological_json_path)
    documents_dir = os.path.join(base_dir, "documents")
    os.makedirs(documents_dir, exist_ok=True)
    
    # Setup temp download directory for PDFs (shared across all documents)
    download_dir = tempfile.mkdtemp()
    
    # Generate unique port for this job to avoid conflicts
    import hashlib
    job_hash = hashlib.md5(chronological_json_path.encode()).hexdigest()[:8]
    unique_port = 9222 + int(job_hash, 16) % 1000  # Port range 9222-10222
    
    # Create a single Chrome driver instance for all documents
    print(f"🚀 Initializing Chrome driver for document retrieval on port {unique_port}...")
    driver = None
    
    try:
        driver = create_stealth_driver(download_dir, port=unique_port)
        print("✅ Chrome driver initialized successfully")
        
        # Retrieve each document using the shared driver
        results = []
        for i, doc in enumerate(documents_chronological):
            print(f"Processing document {i+1}/{len(documents_chronological)}: {doc.get('name', 'Unknown')}")
            result = parse_web_document_selenium_with_driver(doc['url'], documents_dir, driver, download_dir)
            results.append({
                "document": doc,
                "result": result
            })
            print(result)
            
            # Reduced delay between documents since we're reusing the driver
            if i < len(documents_chronological) - 1:  # Don't wait after the last document
                wait_with_random_delay(0.5, 1)  # Reduced from 1-3 to 0.5-1 seconds
        
        # Save retrieval results log
        log_file = os.path.join(base_dir, "retrieval_log.json")
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"✅ All documents retrieved and saved to: {documents_dir}")
        print(f"📋 Retrieval log saved to: {log_file}")
        
        return documents_dir
        
    except Exception as e:
        print(f"❌ Error during document retrieval: {e}")
        raise e
        
    finally:
        # Clean up: close driver and remove temp directory
        if driver:
            try:
                print("🔄 Cleaning up Chrome driver...")
                driver.quit()
                print("✅ Chrome driver closed successfully")
            except Exception as e:
                print(f"⚠️ Warning: Error closing Chrome driver: {e}")
        
        try:
            shutil.rmtree(download_dir)
            print("✅ Temporary download directory cleaned up")
        except Exception as e:
            print(f"⚠️ Warning: Error cleaning up temp directory: {e}")


__all__ = ["retrieve_documents"]
