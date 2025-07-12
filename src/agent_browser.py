import urllib.parse
import asyncio
import logging
import json
import os
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page
from openai import OpenAI
from datetime import datetime
import pickle
import random
from enum import IntEnum
from fastapi import FastAPI
from pydantic import BaseModel
try:
    from .constants import LENS_SELECTORS, SYSTEM_PROMPT, SMART_CLICK_PROMPT, SMART_FILL_PROMPT, BROWSER_OPTIONS  # type: ignore
    from .slack import send_custom_msg  # type: ignore
except ImportError:
    from constants import LENS_SELECTORS, SYSTEM_PROMPT, SMART_CLICK_PROMPT, SMART_FILL_PROMPT, BROWSER_OPTIONS  # type: ignore
    from slack import send_custom_msg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StatusCode(IntEnum):
    SUCCESS = 200
    NO_MATCHES = 404
    RATE_LIMITED = 429
    IP_BLOCKED = 403
    TIMEOUT = 408
    INVALID_URL = 400
    SERVER_ERROR = 500
    NETWORK_ERROR = 502
    PROXY_ERROR = 503
    AI_ERROR = 507
    UNKNOWN_ERROR = 520


# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
LENS_URL = "https://lens.google.com/upload"

# Learning system files
LEARNING_DATA_FILE = "selector_learning_data.json"
SCRIPT_CACHE_FILE = "script_cache.pkl"

# Pydantic Models


class LensSearchRequest(BaseModel):
    image_url: str
    search_type: str = "all"


class LensSearchResponse(BaseModel):
    status_code: int
    message: str
    result: Dict[str, Any]
    total_results: int
    status: str


# FastAPI App
app = FastAPI(title="Google Lens API", version="1.0.0")


class SelectorLearningSystem:
    """System to learn and prioritize successful selectors."""

    def __init__(self):
        self.selector_success_history = self.load_learning_data()
        self.script_cache = self.load_script_cache()

    def load_learning_data(self) -> Dict:
        """Load historical selector success data."""
        try:
            if os.path.exists(LEARNING_DATA_FILE):
                with open(LEARNING_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    return data
        except Exception as e:
            logger.warning(f"Could not load learning data: {e}")
        return {}

    def save_learning_data(self):
        """Save selector success history."""
        try:
            with open(LEARNING_DATA_FILE, 'w') as f:
                json.dump(self.selector_success_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")

    def load_script_cache(self) -> Dict:
        """Load cached AI-generated scripts."""
        try:
            if os.path.exists(SCRIPT_CACHE_FILE):
                with open(SCRIPT_CACHE_FILE, 'rb') as f:
                    data = pickle.load(f)
                    return data
        except Exception as e:
            logger.warning(f"Could not load script cache: {e}")
        return {}

    def save_script_cache(self):
        """Save cached AI-generated scripts."""
        try:
            with open(SCRIPT_CACHE_FILE, 'wb') as f:
                pickle.dump(self.script_cache, f)
        except Exception as e:
            logger.error(f"Failed to save script cache: {e}")

    def record_selector_success(self, element_type: str, selector: str, success: bool):
        """Record whether a selector worked for an element type."""
        if element_type not in self.selector_success_history:
            self.selector_success_history[element_type] = {}

        if selector not in self.selector_success_history[element_type]:
            self.selector_success_history[element_type][selector] = {
                'success_count': 0,
                'failure_count': 0,
                'last_used': None,
                'success_rate': 0.0
            }

        entry = self.selector_success_history[element_type][selector]
        entry['last_used'] = datetime.now().isoformat()

        if success:
            entry['success_count'] += 1
        else:
            entry['failure_count'] += 1

        # Update success rate
        total_attempts = entry['success_count'] + entry['failure_count']
        entry['success_rate'] = entry['success_count'] / \
            total_attempts if total_attempts > 0 else 0.0

    def get_prioritized_selectors(self, element_type: str, default_selectors: List[str]) -> List[str]:
        """Get selectors prioritized by success rate and recency."""
        learned_selectors = []

        if element_type in self.selector_success_history:
            # Sort by success rate (descending) and then by recency
            sorted_selectors = sorted(
                self.selector_success_history[element_type].items(),
                key=lambda x: (x[1]['success_rate'], x[1]['last_used']),
                reverse=True
            )

            # Only include selectors with decent success rate
            learned_selectors = [
                selector for selector, data in sorted_selectors
                if data['success_rate'] > 0.3  # At least 30% success rate
            ]

        # Combine learned selectors (high priority) with default selectors
        all_selectors = learned_selectors + \
            [s for s in default_selectors if s not in learned_selectors]

        return all_selectors

    def cache_script(self, element_type: str, context_hash: str, script: str):
        """Cache an AI-generated script."""
        cache_key = f"{element_type}_{context_hash}"
        self.script_cache[cache_key] = {
            'script': script,
            'created_at': datetime.now().isoformat(),
            'usage_count': 0
        }

    def get_cached_script(self, element_type: str, context_hash: str) -> Optional[str]:
        """Get cached script if available."""
        cache_key = f"{element_type}_{context_hash}"
        if cache_key in self.script_cache:
            self.script_cache[cache_key]['usage_count'] += 1
            script = self.script_cache[cache_key]['script']
            return script
        return None


# Initialize learning system
learning_system = SelectorLearningSystem()


async def ask_agent_for_playwright_script(task: str, page_context: str = None) -> str:
    """Ask AI agent to generate complete Playwright script for a specific task."""
    logger.info(f"Asking AI agent for Playwright script for task: {task}")
    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": task}
    ]

    if page_context:
        messages.append(
            {"role": "user", "content": f"Page HTML context: {page_context[:6000]}"})

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=1000,
            temperature=0.1,
        )

        script = response.choices[0].message.content.strip()
        # Extract just the function code
        if "```python" in script:
            script = script.split("```python")[1].split("```")[0].strip()
        elif "```" in script:
            script = script.split("```")[1].strip()

        return script

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise Exception(f"AI_ERROR: {e}")


async def execute_ai_script(page: Page, script: str, *args) -> bool:
    """Execute AI-generated Playwright script."""
    try:
        # Create a local namespace with necessary imports
        local_namespace = {
            'page': page,
            'logger': logger,
            'asyncio': asyncio,
            'args': args
        }

        # Execute the script
        exec(script, globals(), local_namespace)

        # Find and call the function (assume it's the first async function defined)
        func_name = None
        for name, obj in local_namespace.items():
            if callable(obj) and asyncio.iscoroutinefunction(obj) and name != 'page':
                func_name = name
                break

        if func_name:
            result = await local_namespace[func_name](page, *args)
            return result
        else:
            return False

    except Exception as e:
        return False


async def get_page_html_context(page: Page) -> str:
    """Get relevant HTML context for AI agent."""
    try:
        html_content = await page.content()
        return html_content
    except Exception as e:
        return ""


async def get_locator_from_selector(page: Page, selector: str):
    """Helper to get a Playwright Locator from a selector string."""
    if selector.startswith('role='):
        parts = selector.split('[name="', 1)
        role_part = parts[0].replace('role=', '')
        role = role_part.split('[')[0]
        name = parts[1].rstrip('"]') if len(parts) > 1 else None

        if name:
            return page.getByRole(role, name=name)
        else:
            return page.getByRole(role)
    elif selector.startswith('text='):
        return page.getByText(selector.replace('text=', ''))
    else:
        return page.locator(selector)


async def smart_click(page: Page, element_type: str, element_name: str) -> bool:
    """Intelligently click an element using learning system and AI scripts."""

    # Add human-like behavior before clicking
    await add_human_like_behavior(page)

    default_selectors = LENS_SELECTORS.get(element_type, [])
    prioritized_selectors = learning_system.get_prioritized_selectors(
        element_type, default_selectors)

    # Strategy 1: Try learned and default selectors
    for i, selector in enumerate(prioritized_selectors):
        try:
            locator = await get_locator_from_selector(page, selector)

            # Add human-like delay before clicking
            await page.wait_for_timeout(random.randint(500, 1000))

            await locator.click(timeout=5000)
            await page.wait_for_timeout(random.randint(500, 1000))

            learning_system.record_selector_success(
                element_type, selector, True)
            logger.info(f"Successfully clicked the '{element_name}' element.")
            return True

        except Exception as e:
            logger.warning(
                f"Failed to click the '{element_name}' element: {e}")
            learning_system.record_selector_success(
                element_type, selector, False)
            continue

    # Strategy 2: Try cached AI script
    html_context = await get_page_html_context(page)
    context_hash = str(hash(html_context))

    cached_script = learning_system.get_cached_script(
        element_type, context_hash)
    if cached_script:
        logger.info(f"Executing cached AI script for {element_name}")
        if await execute_ai_script(page, cached_script):
            return True

    # Strategy 3: Generate new AI script
    try:
        task = SMART_CLICK_PROMPT.format(
            element_name=element_name, element_type=element_type, type=element_type.replace('_', ' '))

        ai_script = await ask_agent_for_playwright_script(task, html_context)

        if await execute_ai_script(page, ai_script):
            learning_system.cache_script(element_type, context_hash, ai_script)
            return True
        else:
            logger.warning(f"AI script failed for {element_name}")

    except Exception as e:
        logger.error(
            f"AI script generation/execution failed for {element_name}: {e}")

    return False


async def smart_fill(page: Page, element_type: str, value: str) -> bool:
    """Intelligently fill an input field using learning system and AI scripts."""

    default_selectors = LENS_SELECTORS.get(element_type, [])
    prioritized_selectors = learning_system.get_prioritized_selectors(
        element_type, default_selectors)

    # Strategy 1: Try learned and default selectors
    for i, selector in enumerate(prioritized_selectors):
        try:
            locator = await get_locator_from_selector(page, selector)

            await locator.fill(value, timeout=3000)
            await page.wait_for_timeout(500)

            learning_system.record_selector_success(
                element_type, selector, True)
            return True

        except Exception as e:
            learning_system.record_selector_success(
                element_type, selector, False)
            continue

    # Strategy 2: Try cached AI script
    html_context = await get_page_html_context(page)
    context_hash = str(hash(html_context))

    cached_script = learning_system.get_cached_script(
        element_type, context_hash)
    if cached_script:
        if await execute_ai_script(page, cached_script, value):
            return True

    # Strategy 3: Generate new AI script
    try:
        logger.info(f"Generating AI script for filling {element_type}")
        task = SMART_FILL_PROMPT

        ai_script = await ask_agent_for_playwright_script(task, html_context)

        if await execute_ai_script(page, ai_script, value):
            learning_system.cache_script(element_type, context_hash, ai_script)
            return True
        else:
            logger.warning(f"AI script failed for filling {element_type}")

    except Exception as e:
        logger.error(
            f"AI script generation/execution failed for filling {element_type}: {e}")

    return False


async def extract_external_links(page: Page, tab_name: str) -> List[str]:
    """Extract all external links from the current page."""

    try:
        await page.wait_for_timeout(1000)

        links = await page.evaluate("""
            () => {
                const links = [];
                const anchors = document.querySelectorAll('a[href]');

                anchors.forEach(anchor => {
                    const href = anchor.href;
                    if (href &&
                        href.startsWith('http') &&
                        !href.includes('google.co.in') &&
                        !href.includes('google.com') &&
                        !href.includes('gstatic.com') &&
                        !href.includes('googleusercontent.com') &&
                        !href.includes('lens.google.com') &&
                        !href.includes('data:')) {
                        links.push(href);
                    }
                });

                return [...new Set(links)];
            }
        """)
        return links

    except Exception as e:
        return []


async def ask_ai_for_simple_script(page: Page, task: str) -> str:
    """Ask AI to generate a simple extraction script."""

    # Get page HTML for context
    try:
        html_content = await page.content()
        # Take first 3000 characters for context
        html_context = html_content[:3000]
    except:
        html_context = ""

    prompt = f"""
You are a Playwright expert. Write a simple JavaScript function that runs in the browser to extract product links from Google Lens results.

Task: {task}

The function should:
1. Find all external product links (exclude Google/Google-related domains)
2. Focus on actual product/shopping links that lead to e-commerce sites
3. Return a clean array of unique URLs only

Exclude these domains:
- google.co.in, google.com, google.co.in, google.co.uk (all Google domains)
- gstatic.com, googleusercontent.com
- lens.google.com
- youtube.com, youtu.be
- Any data: or blob: URLs

Return ONLY the JavaScript code, no explanations.

Example format:
```javascript
() => {{
    const links = [];
    const anchors = document.querySelectorAll('a[href^="http"]');

    const excludedDomains = [
        'google.com', 'google.co', 'gstatic.com', 'googleusercontent.com',
        'lens.google.com', 'youtube.com', 'youtu.be', 'google.co.in'
    ];

    anchors.forEach(link => {{
        const href = link.href;
        if (href && href.startsWith('http')) {{
            const isExcluded = excludedDomains.some(domain => href.includes(domain));
            if (!isExcluded && !href.includes('data:') && !href.includes('blob:')) {{
                links.push(href);
            }}
        }}
    }});

    return [...new Set(links)];
}}
```

Current page context: {html_context}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.1,
        )

        script = response.choices[0].message.content.strip()

        # Extract JavaScript code
        if "```javascript" in script:
            script = script.split("```javascript")[1].split("```")[0].strip()
        elif "```" in script:
            script = script.split("```")[1].strip()

        return script

    except Exception as e:
        return ""


async def extract_with_ai(page: Page, tab_name: str) -> List[str]:
    """Extract product links using AI-generated script."""

    task = f"Extract product links from Google Lens {tab_name} results"
    script = await ask_ai_for_simple_script(page, task)

    if not script:
        return []

    try:
        # Execute the JavaScript function on the page
        links = await page.evaluate(script)

        if isinstance(links, list):
            # Clean and validate links
            valid_links = []
            for link in links:
                if isinstance(link, str):
                    link = link.strip()
                    if link and link.startswith('http'):
                        valid_links.append(link)
                elif isinstance(link, dict) and 'link' in link:
                    # Handle case where AI still returns objects
                    link_url = str(link.get('link', '')).strip()
                    if link_url and link_url.startswith('http'):
                        valid_links.append(link_url)

            # Remove duplicates
            return list(set(valid_links))
        else:
            return []

    except Exception as e:
        return []


async def extract_with_predefined_selectors(page: Page, tab_name: str) -> List[Dict[str, Any]]:
    """Extract product data using predefined selectors."""

    try:
        await page.wait_for_timeout(1000)

        # Simple JavaScript to extract external links
        links = await page.evaluate("""
            () => {
                const links = [];
                const anchors = document.querySelectorAll('a[href^="http"]');

                anchors.forEach(link => {
                    const href = link.href;
                    if (href &&
                        !href.includes('google.co.in') &&
                        !href.includes('google.com') &&
                        !href.includes('gstatic.com') &&
                        !href.includes('googleusercontent.com') &&
                        !href.includes('lens.google.com')) {

                        links.push(href);
                    }
                });

                // Remove duplicates
                return [...new Set(links)];
            }
        """)

        # Add tab name to each product
        return links

    except Exception as e:
        return []


async def add_human_like_behavior(page: Page):
    """Add random human-like mouse movements and scrolling."""
    import random

    try:
        # Random mouse movement
        await page.mouse.move(
            random.randint(100, 800),
            random.randint(100, 600)
        )

        # Random small scroll
        await page.mouse.wheel(0, random.randint(-100, 100))

        # Random tiny delay
        await page.wait_for_timeout(random.randint(500, 1500))

    except Exception as e:
        logger.debug(f"Human-like behavior failed: {e}")


async def extract_product_data(page: Page, tab_name: str) -> List[Dict[str, Any]]:
    """
    SIMPLIFIED EXTRACTION FLOW:
    1. Try predefined selectors first
    2. If that fails or returns empty, use AI
    """

    # Step 0: Check for no matches
    if await check_for_no_matches(page):
        return []

    # Step 1: Try predefined selectors
    products = await extract_with_predefined_selectors(page, tab_name)

    if products and len(products) > 0:
        return products

    # Step 2: Fallback to AI
    products = await extract_with_ai(page, tab_name)

    if products and len(products) > 0:
        return products

    # Step 3: Final check - if still no results, verify it's not a "no matches" case
    if await check_for_no_matches(page):
        return []

    return []


async def wait_for_results(page: Page, timeout: int = 1000) -> bool:
    """Wait for search results to appear."""

    try:
        await page.wait_for_selector(
            'div[data-sokoban-container], role=tab[name="Visual matches"], role=button[name="Visual matches"], a[href^="http"]:not([href*="google.com"])',
            state='visible',
            timeout=timeout
        )
        await page.wait_for_timeout(3000)
        return True
    except Exception as e:
        return False


async def check_for_no_matches(page: Page) -> bool:
    """Check if the page shows 'No matches found' message."""

    try:
        # Wait a bit for content to load
        await page.wait_for_timeout(2000)

        # Check for various "no matches" indicators
        no_matches_selectors = [
            'text="No matches for your search"',
            'text="No results found"',
            'text="No matches found"',
            'text="To get better results, try changing the search area"',
            'text="sending a different image"',
            '[data-test-id="no-results"]',
            '.no-results',
            '.empty-state',
            '*:has-text("No matches for your search")',
            '*:has-text("No results found")',
            '*:has-text("better results")',
            '*:has-text("different image")',
        ]

        for selector in no_matches_selectors:
            try:
                element = await page.locator(selector).first
                if await element.is_visible(timeout=1000):
                    return True
            except:
                continue

        # Check page content for no matches text
        try:
            page_content = await page.content()
            no_matches_phrases = [
                "No matches for your search",
                "No results found",
                "No matches found",
                "try changing the search area",
                "sending a different image",
                "better results",
                "different image"
            ]

            for phrase in no_matches_phrases:
                if phrase.lower() in page_content.lower():
                    return True
        except Exception as e:
            logger.warning(f"Failed to check page content: {e}")

        # Check if there are very few external links (could indicate no results)
        try:
            external_links = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href^="http"]');
                    const external = Array.from(links).filter(link =>
                        !link.href.includes('google.co') &&
                        !link.href.includes('gstatic.com') &&
                        !link.href.includes('googleusercontent.com')
                    );
                    return external.length;
                }
            """)

            if external_links <= 1:  # Very few or no external links
                return True

        except Exception as e:
            logger.warning(f"Failed to count external links: {e}")

        return False

    except Exception as e:
        return False


async def lens_search(image_url: str, search_type: str = "all") -> Dict[str, Any]:
    """Perform Google Lens search using direct URL navigation first, fallback to manual method."""

    # Validate image URL
    if not image_url or not image_url.startswith(('http://', 'https://')):
        error_msg = f"Invalid image URL provided: {image_url}"
        logger.error(error_msg)
        send_custom_msg(f"🚨 INVALID URL ERROR: {error_msg}")
        return {
            "status_code": StatusCode.INVALID_URL,
            "message": "Invalid image URL provided",
            "result": {},
            "total_results": 0,
            "status": "error"
        }

    async with async_playwright() as p:
        browser = None
        context = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=BROWSER_OPTIONS
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            # Set page timeout
            page.set_default_timeout(30000)

            encoded_url = urllib.parse.quote(image_url, safe='')
            direct_lens_url = f"https://lens.google.com/uploadbyurl?url={encoded_url}&ep=cntpubu&hl=en-IN&st={int(datetime.now().timestamp() * 1000)}&re=df&s=4"

            try:
                await page.goto(direct_lens_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)

                # Check for blocking/captcha
                page_content = await page.content()
                if "unusual traffic" in page_content.lower() or "captcha" in page_content.lower():
                    logger.warning(
                        "Direct navigation blocked, trying fallback method")
                    raise Exception("Direct navigation blocked")

            except Exception as e:
                logger.warning(
                    f"Direct navigation failed: {e}. Falling back to manual method...")

                # Strategy 2: Fallback to manual method
                logger.info("Using manual navigation method...")
                await page.goto(LENS_URL, wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)

                if not await smart_fill(page, "url_input", image_url):
                    error_msg = "Failed to fill URL input field"
                    logger.error(error_msg)
                    return {
                        "status_code": StatusCode.SERVER_ERROR,
                        "message": error_msg,
                        "result": {},
                        "total_results": 0,
                        "status": "error"
                    }

                if not await smart_click(page, "search_button", "Search"):
                    error_msg = "Failed to click search button"
                    return {
                        "status_code": StatusCode.SERVER_ERROR,
                        "message": error_msg,
                        "result": {},
                        "total_results": 0,
                        "status": "error"
                    }

                if not await wait_for_results(page):
                    error_msg = "Results timeout - page may not have loaded completely"

            # Check for rate limiting or IP blocking
            page_content = await page.content()
            if "unusual traffic" in page_content.lower() or "captcha" in page_content.lower():
                error_msg = "Rate limited or IP blocked by Google"
                send_custom_msg(f"🚨 RATE LIMIT ERROR: {error_msg}")
                return {
                    "status_code": StatusCode.RATE_LIMITED,
                    "message": error_msg,
                    "result": {},
                    "total_results": 0,
                    "status": "rate_limited"
                }

            # Check for "No matches found" case
            no_matches_found = await check_for_no_matches(page)
            if no_matches_found:
                return {
                    "status_code": StatusCode.NO_MATCHES,
                    "message": "No matches found for your search",
                    "result": {"message": "No matches found for your search"},
                    "total_results": 0,
                    "status": "no_matches"
                }

            results = {}

            # Determine tabs to process based on search_type
            tabs_to_process = []
            if search_type == "both":
                tabs_to_process = [
                    ("visual_matches_tab", "Visual matches"),
                    ("exact_matches_tab", "Exact matches")
                ]
            elif search_type == "visual_matches":
                tabs_to_process = [("visual_matches_tab", "Visual matches")]
            elif search_type == "exact_matches":
                tabs_to_process = [("exact_matches_tab", "Exact matches")]
            elif search_type == "all":
                # For "all", try to extract from current page first, then try specific tabs
                tabs_to_process = [("current_page", "All")]
            else:
                return {
                    "status_code": StatusCode.INVALID_URL,
                    "message": "Invalid search type provided",
                    "result": {},
                    "total_results": 0,
                    "status": "error"
                }

            # Process tabs
            for tab_type, tab_name in tabs_to_process:
                # Add random delay between tab operations
                await page.wait_for_timeout(random.randint(1000, 2000))

                # If it's not current page, try to click the tab
                if tab_type != "current_page":
                    if await smart_click(page, tab_type, tab_name):
                        await page.wait_for_timeout(random.randint(1000, 2000))

                # Check for no matches in current tab/page
                tab_no_matches = await check_for_no_matches(page)
                if tab_no_matches:
                    key_name = tab_name.lower().replace(' ', '_')
                    results[key_name] = []
                    continue

                # Extract data from current page
                links = await extract_product_data(page, tab_name)
                key_name = tab_name.lower().replace(' ', '_')
                results[key_name] = links

            # Calculate total results
            total_results = sum(len(links) for links in results.values())

            # Save learning data after successful run
            learning_system.save_learning_data()
            learning_system.save_script_cache()

            if total_results > 0:
                return {
                    "status_code": StatusCode.SUCCESS,
                    "message": "Search completed successfully",
                    "result": results,
                    "total_results": total_results,
                    "status": "success"
                }
            else:
                return {
                    "status_code": StatusCode.NO_MATCHES,
                    "message": "No results found",
                    "result": results,
                    "total_results": 0,
                    "status": "no_results"
                }

        except asyncio.TimeoutError:
            error_msg = "Operation timeout"
            logger.error(error_msg)
            send_custom_msg(f"🚨 TIMEOUT ERROR: {error_msg}")
            return {
                "status_code": StatusCode.TIMEOUT,
                "message": error_msg,
                "result": {},
                "total_results": 0,
                "status": "timeout"
            }
        except Exception as e:
            error_str = str(e)
            if "AI_ERROR" in error_str:
                error_msg = f"AI script generation failed: {error_str}"
                logger.error(error_msg)
                send_custom_msg(f"🚨 AI ERROR: {error_msg}")
                return {
                    "status_code": StatusCode.AI_ERROR,
                    "message": error_msg,
                    "result": {},
                    "total_results": 0,
                    "status": "ai_error"
                }
            elif "network" in error_str.lower():
                error_msg = f"Network error: {error_str}"
                logger.error(error_msg)
                send_custom_msg(f"🚨 NETWORK ERROR: {error_msg}")
                return {
                    "status_code": StatusCode.NETWORK_ERROR,
                    "message": error_msg,
                    "result": {},
                    "total_results": 0,
                    "status": "network_error"
                }
            else:
                error_msg = f"Unknown error: {error_str}"
                logger.error(error_msg)
                send_custom_msg(f"🚨 UNKNOWN ERROR: {error_msg}")
                return {
                    "status_code": StatusCode.UNKNOWN_ERROR,
                    "message": error_msg,
                    "result": {},
                    "total_results": 0,
                    "status": "unknown_error"
                }
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
            logger.info("Browser context closed")
