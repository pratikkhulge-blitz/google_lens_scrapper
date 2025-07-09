from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Literal
import logging
import random
import time
import os
import platform
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager, ChromeType
from urllib.parse import quote

WORKING_PROXY = [
    '8.210.110.110:3128',
    '47.74.152.29:8888',
    '103.152.112.162:80',
    '185.199.84.161:53281',
    '103.168.53.157:41317',
    '185.108.140.69:8080',
    '103.152.112.145:80',
    '8.219.97.248:80',
    '47.74.64.65:8080',
    '103.152.112.157:80'
]

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Google Lens API", version="1.0.0")

# Models


class LensRequest(BaseModel):
    image_url: HttpUrl
    search_type: Literal["exact_matches", "visual_matches", "all"] = "all"


class LensResult(BaseModel):
    url: str
    title: str
    description: str
    thumbnail: Optional[str] = None


class LensResponse(BaseModel):
    success: bool
    results: List[LensResult]
    total_results: int
    search_type: str
    message: Optional[str] = None


class PlatformUtils:
    """Utility class for platform-specific operations"""

    @staticmethod
    def get_system_info():
        """Get system information for driver selection"""
        system = platform.system().lower()
        machine = platform.machine().lower()

        info = {
            'system': system,
            'machine': machine,
            'is_linux': system == 'linux',
            'is_windows': system == 'windows',
            'is_mac': system == 'darwin',
            'is_arm': 'arm' in machine or 'aarch64' in machine,
            'is_x64': 'x86_64' in machine or 'amd64' in machine
        }

        logger.info(f"System info: {info}")
        return info

    @staticmethod
    def check_chrome_installed():
        """Check if Chrome is installed on the system"""
        try:
            system_info = PlatformUtils.get_system_info()

            if system_info['is_linux']:
                # Check common Chrome paths on Linux
                chrome_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/bin/chromium-browser',
                    '/usr/bin/chromium'
                ]

                for path in chrome_paths:
                    if os.path.exists(path):
                        logger.info(f"Chrome found at: {path}")
                        return True

                # Try to find Chrome using which command
                try:
                    result = subprocess.run(['which', 'google-chrome'],
                                            capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.info(
                            f"Chrome found via which: {result.stdout.strip()}")
                        return True
                except:
                    pass

            elif system_info['is_windows']:
                # Check common Chrome paths on Windows
                chrome_paths = [
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                    os.path.expanduser(
                        r'~\AppData\Local\Google\Chrome\Application\chrome.exe')
                ]

                for path in chrome_paths:
                    if os.path.exists(path):
                        logger.info(f"Chrome found at: {path}")
                        return True

            elif system_info['is_mac']:
                # Check Chrome path on macOS
                chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                if os.path.exists(chrome_path):
                    logger.info(f"Chrome found at: {chrome_path}")
                    return True

            logger.warning("Chrome not found on system")
            return False

        except Exception as e:
            logger.error(f"Error checking Chrome installation: {e}")
            return False


class GoogleLensService:
    def __init__(self):
        self.current_proxy_index = 0
        self.system_info = PlatformUtils.get_system_info()
        self.chrome_installed = PlatformUtils.check_chrome_installed()

        if not self.chrome_installed:
            logger.error(
                "Chrome is not installed. Please install Chrome before using this service.")

    def get_next_proxy(self):
        """Get next proxy from rotation list"""
        if not WORKING_PROXY:
            return None

        proxy = WORKING_PROXY[self.current_proxy_index]
        self.current_proxy_index = (
            self.current_proxy_index + 1) % len(WORKING_PROXY)
        return proxy

    def setup_driver(self, use_proxy=False):
        """Setup Chrome driver with platform-specific configurations"""
        if not self.chrome_installed:
            raise HTTPException(
                status_code=500,
                detail="Chrome is not installed. Please install Chrome to use this service."
            )

        options = Options()

        # Common Chrome options
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--window-size=1920,1080')

        # Platform-specific configurations
        if self.system_info['is_linux']:
            # Linux-specific options
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--remote-debugging-port=9222')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--single-process')

            # Set Chrome binary path for Linux
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium'
            ]

            for path in chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    logger.info(f"Using Chrome binary: {path}")
                    break

        elif self.system_info['is_windows']:
            # Windows-specific options
            options.add_argument('--disable-logging')

        elif self.system_info['is_mac']:
            # macOS-specific options
            options.add_argument('--disable-dev-shm-usage')

            # Set Chrome binary path for macOS
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            if os.path.exists(chrome_path):
                options.binary_location = chrome_path

        # Anti-detection measures
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option(
            'excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        # Add proxy if requested and available
        if use_proxy and WORKING_PROXY:
            proxy = self.get_next_proxy()
            if proxy:
                options.add_argument(f'--proxy-server=http://{proxy}')
                logger.info(f"Using proxy: {proxy}")

        try:
            # Try to use webdriver-manager for automatic driver management
            try:
                chrome_type = ChromeType.GOOGLE
                driver_path = ChromeDriverManager(
                    chrome_type=chrome_type).install()

                if not os.path.exists(driver_path):
                    raise Exception(f"Driver not found at {driver_path}")

                if not self.system_info['is_windows']:
                    os.chmod(driver_path, 0o755)

                service = Service(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=options)

                logger.info(
                    f"Chrome driver initialized successfully with webdriver-manager: {driver_path}")

            except Exception as e:
                logger.warning(f"webdriver-manager failed: {e}")
                driver = webdriver.Chrome(options=options)
                logger.info(
                    "Chrome driver initialized successfully (fallback to PATH)")

        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Chrome driver: {str(e)}. Please ensure Chrome and ChromeDriver are properly installed."
            )

        # Set timeouts
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)

        # Anti-detection script
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'language', {
                    get: () => 'en-US'
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Linux x86_64'
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 4
                });
                window.chrome = {
                    runtime: {}
                };
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' })
                    })
                });
            '''
        })

        return driver

    def _set_india_location_preferences(self, driver):
        """Set India-specific location preferences in the browser"""
        try:
            # Set geolocation to India (New Delhi coordinates)
            location_params = {
                "latitude": 28.6139,
                "longitude": 77.2090,
                "accuracy": 100
            }

            # Set timezone for India (IST)
            timezone_params = {
                "timezoneId": "Asia/Kolkata"
            }

            # Execute Chrome DevTools Protocol commands
            driver.execute_cdp_cmd(
                "Emulation.setGeolocationOverride", location_params)
            driver.execute_cdp_cmd(
                "Emulation.setTimezoneOverride", timezone_params)

            # Set accept language header to English (India)
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": driver.execute_script("return navigator.userAgent") + " en-IN,en-GB,en-US,en",
                "acceptLanguage": "en-IN,en-GB,en-US,en;q=0.9"
            })

            logger.info("Set India-specific location preferences")
            return True

        except Exception as e:
            logger.warning(f"Could not set India location preferences: {e}")
            return False

    def handle_cookie_consent(self, driver):
        """Handle cookie consent dialogs if they appear"""
        try:
            consent_selectors = [
                "button:has-text('Accept all')",
                "button:has-text('I agree')",
                "button:has-text('Accept')",
                "button:has-text('Agree')",
                "button[aria-label*='Accept']",
                "button[aria-label*='Agree']",
                "button[onclick*='accept']",
                "button#L2AGLb",
                "button.tHlp8d",
                "div[role='dialog'] button:last-child"
            ]

            for selector in consent_selectors:
                try:
                    button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if button.is_displayed():
                        button.click()
                        logger.info("Accepted cookie consent")
                        time.sleep(1)
                        return True
                except Exception as e:
                    continue

            logger.info("No cookie consent dialog found or could not accept")
            return False

        except Exception as e:
            logger.warning(f"Error handling cookie consent: {e}")
            return False

    def build_lens_url(self, image_url: str, search_type: str):
        """Build Google Lens URL based on search type"""
        encoded_url = quote(str(image_url), safe='')
        timestamp = int(time.time() * 1000)

        # India-specific parameters
        gl_param = 'in'
        hl_param = 'en-IN'
        lr_param = 'lang_en|countryIN'
        cr_param = 'countryIN'

        # Base URL construction
        base_url = "https://lens.google.com/uploadbyurl"

        # Common parameters
        common_params = {
            'url': encoded_url,
            'ep': 'cntpubu',
            'hl': hl_param,
            'gl': gl_param,
            'lr': lr_param,
            'cr': cr_param,
            'st': timestamp,
            'sa': 'X',
            'biw': '1440',
            'bih': '778'
        }

        if search_type == "exact_matches":
            # For exact matches, we need to add specific parameters
            # These parameters are derived from the HTML structure you provided
            common_params.update({
                'lns_mode': 'un',
                'source': 'lns.web.cntpubu',
                'udm': '48',
                're': 'df',
                's': '4'
            })
        elif search_type == "visual_matches":  # visual_matches
            # For visual matches, use different parameters
            common_params.update({
                'lns_mode': 'visual',
                'source': 'lns.web.cntpubu',
                'udm': '44',
                're': 'df',
                's': '4'
            })
        else:
            common_params.update({})
            
        # Build the URL
        url_parts = [base_url + '?']
        for key, value in common_params.items():
            url_parts.append(f"{key}={value}&")

        return ''.join(url_parts).rstrip('&')

    def navigate_to_search_type(self, driver, search_type: str):
        """Navigate to specific search type (exact_matches or visual_matches)"""
        try:
            if search_type == "exact_matches":
                # Look for "Exact matches" tab
                exact_matches_selectors = [
                    "//div[contains(text(), 'Exact matches')]",
                    "//a[contains(text(), 'Exact matches')]",
                    "//div[@jsname='bVqjv' and contains(text(), 'Exact matches')]",
                    "//div[contains(@class, 'YmvwI') and contains(text(), 'Exact matches')]"
                ]

                for selector in exact_matches_selectors:
                    try:
                        element = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if element.is_displayed():
                            element.click()
                            logger.info("Clicked on 'Exact matches' tab")
                            time.sleep(3)
                            return True
                    except Exception as e:
                        continue

            elif search_type == "visual_matches":
                # Look for "Visual matches" tab
                visual_matches_selectors = [
                    "//div[contains(text(), 'Visual matches')]",
                    "//a[contains(text(), 'Visual matches')]",
                    "//div[@jsname='bVqjv' and contains(text(), 'Visual matches')]",
                    "//div[contains(@class, 'YmvwI') and contains(text(), 'Visual matches')]"
                ]

                for selector in visual_matches_selectors:
                    try:
                        element = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if element.is_displayed():
                            element.click()
                            logger.info("Clicked on 'Visual matches' tab")
                            time.sleep(3)
                            return True
                    except Exception as e:
                        continue

            logger.warning(f"Could not find or click {search_type} tab")
            return False

        except Exception as e:
            logger.error(f"Error navigating to search type {search_type}: {e}")
            return False

    def search_by_image_url(self, driver, image_url: str, search_type: str):
        """Search Google Lens using image URL with specific search type"""
        try:
            # Build the appropriate URL for the search type
            search_url = self.build_lens_url(image_url, search_type)

            # Set location preferences
            self._set_india_location_preferences(driver)
            logger.info(f"Searching with URL: {search_url}")

            # Navigate to the URL
            driver.get(search_url)

            # Handle cookie consent
            self.handle_cookie_consent(driver)

            # Wait for page to load completely
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script(
                    "return document.readyState") == "complete"
            )

            # Additional wait for results to load
            time.sleep(3)

            # Try to navigate to the specific search type if tabs are available
            if not self.navigate_to_search_type(driver, search_type):
                logger.info(f"Using direct URL approach for {search_type}")

            # Check if we have results
            results_indicators = [
                "//div[contains(@class, 'g')]",
                "//div[@data-ved]",
                "//a[contains(@href, 'http') and not(contains(@href, 'google.com'))]",
                "//div[contains(@class, 'sh-dlr__list-result')]"
            ]

            for indicator in results_indicators:
                try:
                    elements = driver.find_elements(By.XPATH, indicator)
                    if elements:
                        logger.info(f"Found {len(elements)} result indicators")
                        return True
                except Exception as e:
                    logger.debug(f"Indicator check failed: {e}")
                    continue

            logger.warning(
                "No result indicators found, but continuing with results extraction")
            return True

        except Exception as e:
            logger.error(f"Search by image URL failed: {e}")
            return False

    def extract_results_by_type(self, driver, search_type: str) -> List[LensResult]:
        """Extract results based on search type with enhanced selectors"""
        results = []

        try:
            # Wait for results to load
            time.sleep(3)

            # Scroll to load more results
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Enhanced JavaScript for better result extraction
            results_data = driver.execute_script("""
                let results = [];
                let processedUrls = new Set();
                
                function getTextContent(element) {
                    if (!element) return '';
                    return element.textContent?.trim() || element.innerText?.trim() || '';
                }
                
                function getImageSrc(element) {
                    if (!element) return '';
                    return element.src || element.getAttribute('data-src') || element.getAttribute('data-original') || '';
                }
                
                // Strategy 1: Look for exact matches specific results
                if (arguments[0] === 'exact_matches') {
                    // Look for exact match results - these often have specific classes
                    const exactMatchResults = document.querySelectorAll('div[data-ved] a[href*="http"]:not([href*="google.com"]):not([href*="gstatic.com"])');
                    
                    exactMatchResults.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href || processedUrls.has(href) || href.includes('google.com') || href.includes('gstatic.com')) return;
                        
                        processedUrls.add(href);
                        
                        let title = getTextContent(link.querySelector('h3')) || getTextContent(link);
                        let description = '';
                        let thumbnail = '';
                        
                        // Find description in parent containers
                        const parent = link.closest('div[data-ved]') || link.closest('div.g');
                        if (parent) {
                            const descElement = parent.querySelector('span[data-ved], div[data-ved] span, .s, .st');
                            if (descElement) {
                                description = getTextContent(descElement);
                            }
                        }
                        
                        // Find thumbnail
                        const img = link.querySelector('img') || link.closest('div').querySelector('img');
                        if (img) {
                            thumbnail = getImageSrc(img);
                        }
                        
                        if (title || description) {
                            results.push({
                                url: href,
                                title: title || 'No title',
                                description: description || 'No description',
                                thumbnail: thumbnail || null
                            });
                        }
                    });
                }
                
                // Strategy 2: Look for visual matches specific results
                if (arguments[0] === 'visual_matches') {
                    // Look for visual match results - these might be in different containers
                    const visualMatchResults = document.querySelectorAll('div.g, div[data-ved] a[href*="http"]:not([href*="google.com"]):not([href*="gstatic.com"])');
                    
                    visualMatchResults.forEach(result => {
                        let link = result.tagName === 'A' ? result : result.querySelector('a[href*="http"]:not([href*="google.com"])');
                        if (!link) return;
                        
                        const href = link.getAttribute('href');
                        if (!href || processedUrls.has(href) || href.includes('google.com') || href.includes('gstatic.com')) return;
                        
                        processedUrls.add(href);
                        
                        let title = getTextContent(link.querySelector('h3')) || getTextContent(link);
                        let description = '';
                        let thumbnail = '';
                        
                        // Find description
                        const parent = link.closest('div.g') || link.closest('div[data-ved]') || link.parentElement;
                        if (parent) {
                            const descElement = parent.querySelector('span[data-ved], div[data-ved] span, .s, .st');
                            if (descElement) {
                                description = getTextContent(descElement);
                            }
                        }
                        
                        // Find thumbnail
                        const img = result.querySelector('img') || link.querySelector('img');
                        if (img) {
                            thumbnail = getImageSrc(img);
                        }
                        
                        if (title || description) {
                            results.push({
                                url: href,
                                title: title || 'No title',
                                description: description || 'No description',
                                thumbnail: thumbnail || null
                            });
                        }
                    });
                }
                
                // Strategy 3: Fallback - Look for any external links if no specific results found
                if (results.length < 3) {
                    const allLinks = document.querySelectorAll('a[href*="http"]:not([href*="google.com"]):not([href*="gstatic.com"]):not([href*="googleusercontent.com"])');
                    
                    allLinks.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href || processedUrls.has(href)) return;
                        
                        processedUrls.add(href);
                        
                        let title = getTextContent(link);
                        let description = '';
                        let thumbnail = '';
                        
                        // Try to find more context
                        const parent = link.closest('div');
                        if (parent) {
                            const siblingText = parent.querySelector('span, div:not(a)');
                            if (siblingText) {
                                description = getTextContent(siblingText);
                            }
                        }
                        
                        if (title && title.length > 5) {
                            results.push({
                                url: href,
                                title: title.substring(0, 200),
                                description: description.substring(0, 500) || 'No description',
                                thumbnail: thumbnail || null
                            });
                        }
                    });
                }
                
                return results;
            """, search_type)

            # Convert to LensResult objects
            for item in results_data:
                if item.get('url') and not any(excluded in item['url'].lower() for excluded in ['google.com', 'gstatic.com', 'googleusercontent.com']):
                    results.append(LensResult(
                        url=item['url'],
                        title=item['title'][:200] if item['title'] else 'No title',
                        description=item['description'][:500] if item['description'] else 'No description',
                        thumbnail=item['thumbnail'] if item['thumbnail'] else None
                    ))

            # Remove duplicates and limit results
            seen_urls = set()
            unique_results = []
            for result in results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_results.append(result)
                    if len(unique_results) >= 500:
                        break

            logger.info(
                f"Extracted {len(unique_results)} unique results for {search_type}")
            return unique_results

        except Exception as e:
            logger.error(f"Error extracting results: {e}")
            return []

    def search_image(self, image_url: str, search_type: str) -> LensResponse:
        """Perform Google Lens search with image URL"""
        driver = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"Search attempt {attempt + 1}/{max_retries}")

                # Setup driver with proxy on retry
                use_proxy = attempt > 0  # Use proxy on retries
                driver = self.setup_driver(use_proxy=use_proxy)

                # Search using image URL
                if not self.search_by_image_url(driver, image_url, search_type):
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        logger.warning(
                            f"Search failed, retrying... (attempt {attempt + 1})")
                        continue
                    else:
                        return LensResponse(
                            success=False,
                            results=[],
                            total_results=0,
                            search_type=search_type,
                            message="Failed to initiate search with image URL after multiple attempts"
                        )

                # Extract results
                results = self.extract_results_by_type(driver, search_type)

                if results:
                    return LensResponse(
                        success=True,
                        results=results,
                        total_results=len(results),
                        search_type=search_type,
                        message=f"Found {len(results)} {search_type.replace('_', ' ')}"
                    )
                elif attempt < max_retries - 1:
                    logger.warning(
                        f"No results found, retrying... (attempt {attempt + 1})")
                    continue
                else:
                    return LensResponse(
                        success=True,
                        results=[],
                        total_results=0,
                        search_type=search_type,
                        message="Search completed but no results found"
                    )

            except Exception as e:
                logger.error(f"Search attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info("Retrying with different configuration...")
                    continue
                else:
                    return LensResponse(
                        success=False,
                        results=[],
                        total_results=0,
                        search_type=search_type,
                        message=f"Search failed after {max_retries} attempts: {str(e)}"
                    )
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None


# Initialize service
lens_service = GoogleLensService()
