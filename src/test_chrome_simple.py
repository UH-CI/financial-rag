#!/usr/bin/env python3
"""
Simple Chrome test to verify Selenium works in Docker
"""
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def test_chrome():
    print("🔍 Testing Chrome in Docker environment...")
    
    # Check if we're in Docker
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV') == 'true'
    print(f"Docker environment detected: {is_docker}")
    
    options = Options()
    
    # Add comprehensive Chrome options for Docker
    chrome_options = [
        '--headless=new',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-software-rasterizer',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI,VizDisplayCompositor',
        '--disable-extensions',
        '--disable-default-apps',
        '--disable-sync',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-networking',
        '--disable-component-extensions-with-background-pages',
        '--disable-client-side-phishing-detection',
        '--disable-hang-monitor',
        '--disable-prompt-on-repost',
        '--disable-web-security',
        '--allow-running-insecure-content',
        '--window-size=1920,1080',
        '--remote-debugging-port=9222',
        '--disable-blink-features=AutomationControlled',
        '--disable-ipc-flooding-protection'
    ]
    
    for option in chrome_options:
        options.add_argument(option)
    
    # Try different approaches
    approaches = [
        ("webdriver-manager", lambda: Service(ChromeDriverManager().install())),
        ("system chromedriver", lambda: None)
    ]
    
    for approach_name, service_func in approaches:
        try:
            print(f"\n🚀 Trying {approach_name}...")
            service = service_func()
            
            if service:
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
            
            print(f"✅ Chrome driver created successfully with {approach_name}")
            
            # Test basic functionality
            driver.get("https://httpbin.org/get")
            print(f"✅ Successfully loaded test page")
            print(f"Page title: {driver.title}")
            
            # Get page source to verify it worked
            page_source = driver.page_source[:200]
            print(f"Page source preview: {page_source}...")
            
            driver.quit()
            print(f"✅ Chrome test completed successfully with {approach_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed with {approach_name}: {e}")
            continue
    
    print("❌ All Chrome approaches failed")
    return False

if __name__ == "__main__":
    success = test_chrome()
    exit(0 if success else 1)
