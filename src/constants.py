LENS_SELECTORS = {
    "url_input": [
        'role=textbox[name="Paste image link"]',
        'input[type="url"]',
        'input[placeholder*="image"]',
        'input[placeholder*="URL"]',
        'input[placeholder*="link"]',
        'input[aria-label*="image"]',
        'input[aria-label*="URL"]',
        'input[aria-label*="link"]',
        'textarea[placeholder*="image"]',
        'textarea[placeholder*="URL"]',
        'div[contenteditable="true"]',
        'input[type="text"]',
        'role=textbox[placeholder*="image link"]'
    ],
    "search_button": [
        'role=button[name="Search"]',
        'button[type="submit"]',
        'button:has-text("Search")',
        'button[aria-label*="Search"]',
        'button[aria-label*="search"]',
        'input[type="submit"]',
        'div[role="button"]:has-text("Search")',
        'span:has-text("Search")',
        'button:has([aria-label*="search"])'
    ],
    "visual_matches_tab": [
        'role=tab[name="Visual matches"]',
        'role=button[name="Visual matches"]',
        'div[role="tab"]:has-text("Visual matches")',
        'button:has-text("Visual matches")',
        'a:has-text("Visual matches")',
        'div[aria-label*="Visual matches"]',
        'span:has-text("Visual matches")',
        'div:has-text("Visual matches")',
        '[data-test*="visual"]',
        'div[role="button"]:has-text("Visual")'
    ],
    "exact_matches_tab": [
        'role=tab[name="Exact matches"]',
        'role=button[name="Exact matches"]',
        'div[role="tab"]:has-text("Exact matches")',
        'button:has-text("Exact matches")',
        'a:has-text("Exact matches")',
        'div[aria-label*="Exact matches"]',
        'span:has-text("Exact matches")',
        'div:has-text("Exact matches")',
        '[data-test*="exact"]',
        'div[role="button"]:has-text("Exact")'
    ]
}

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are a Playwright automation expert. Generate a complete Python async function "
        "that performs the requested task using Playwright. The function should:\n"
        "1. Take 'page' as the first parameter\n"
        "2. Take any additional parameters needed for the task\n"
        "3. Use modern Playwright best practices with proper waits and error handling\n"
        "4. Return True if successful, False if failed\n"
        "5. Include try-except blocks for error handling\n"
        "6. Use page.locator() or page.getByRole() methods\n"
        "7. Include appropriate timeouts and wait strategies\n"
        "8. Add logging statements for debugging\n\n"
        "Example format:\n"
        "```python\n"
        "async def perform_task(page, param1, param2):\n"
        "try:\n"
        "# Your Playwright code here\n"
        "await page.locator('selector').click()\n"
        "return True\n"
        "except Exception as e:\n"
        "logger.error(f'Task failed: {e}')\n"
        "return False\n"
        "```\n\n"
        "Only return the function code, no explanations."
    )
}

SMART_CLICK_PROMPT = (
    "Create a Playwright function to click the '{element_name}' element."
    "\n\n🧠 It is a {type}. The function should be named 'click_{element_type}' "
    "and take a single parameter: (page)."
    "\n\n🧩 The function must:"
    "\n1. Wait for the element to be visible and attached to the DOM."
    "\n2. Locate it reliably using accessible selectors such as role (e.g. role=button[name='{element_name}']) or visible text."
    "\n3. Click the element once it's stable and interactable."
    "\n\n💡 Tip: Prefer role-based or text-based selectors like:"
    "\n- role=button[name='{element_name}']"
    "\n- text='{element_name}'"
    "\n- aria-label or visible content if available"
    "\n\n🔄 Ensure compatibility with dynamic content (e.g. buttons rendered after JS loads)."
    "\n📌 This function is strictly for clicking elements with known labels like 'Search', 'Visual matches', or 'Exact matches'."
)

SMART_FILL_PROMPT = (
    "You are writing a Playwright function to input an image URL on the Google Lens landing page."
    "\n\n📌 The goal is to locate the input field meant for image URLs (not file uploads)."
    "\n\n🔍 Use visual or accessible cues to find the field reliably:"
    "\n- Look for an <input> element with a placeholder like 'Paste image link' or similar."
    "\n- The field is typically located below the upload box (which mentions 'Drag an image') and above the 'Search' button."
    "\n\n🧪 You should:"
    "\n1. Wait for the input to appear on the page."
    "\n2. Clear any existing content."
    "\n3. Type the provided image URL."
    "\n4. Optionally verify the input value after typing."
    "\n\n🧩 Your function should be named based on the input type (e.g., 'fill_image_link_input') and take two arguments: (page, value)."
)

BROWSER_OPTIONS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-blink-features=AutomationControlled',
    '--disable-extensions',
    '--start-maximized',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-logging',
    '--disable-web-security',
    '--disable-features=VizDisplayCompositor',
    '--disable-software-rasterizer',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-features=TranslateUI',
    '--disable-ipc-flooding-protection',
    '--disable-extensions',
    '--disable-notifications',
    '--disable-popup-blocking',
    '--lang=en-IN',
    '--accept-lang=en-IN,en;q=0.9,hi;q=0.8',
    '--disable-automation',
    '--disable-infobars',
    '--disable-default-apps',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-component-update',
    '--disable-sync',
    '--disable-features=VizDisplayCompositor',
    '--profile-directory=Default',
]
