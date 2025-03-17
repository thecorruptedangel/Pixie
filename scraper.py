from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

class PlaywrightWebKitScraper:
    def __init__(self, headless=True):
        # Start Playwright and launch WebKit browser in headless mode
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.webkit.launch(headless=headless)

        # Create a browser context (isolated session)
        self.context = self.browser.new_context()

    def get_page_text_content(self, url):
        # Create a new page within the existing browser context
        page = self.context.new_page()
        stealth_sync(page)  # Use stealth to avoid detection
        
        # Block unnecessary resources like images, stylesheets, and fonts
        def block_resources(route):
            if route.request.resource_type in ['image', 'stylesheet', 'font']:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", block_resources)

        # Navigate to the target website and wait for the DOM to load
        page.goto(url, wait_until='domcontentloaded')

        # Extract and return all visible text content from the body of the page
        page_text = page.inner_text('body')

        # Close the page (browser stays open for reuse)
        page.close()
        return page_text

    def close(self):
        # Close the browser and stop Playwright when finished
        self.browser.close()
        self.playwright.stop()

if __name__ == "__main__":
    # Initialize WebKit scraper (preloads the browser)
    scraper = PlaywrightWebKitScraper()
    print("Loaded")
    # Fetch and print the text content of a webpage
    url = "https://www.google.com/search?q=weather+in+kochi&sourceid=chrome&ie=UTF-8"  # Replace with your target URL
    content = scraper.get_page_text_content(url)
    print(content)

    # # Optionally reuse the scraper for multiple URLs
    # another_url = "https://another-example.com"
    # content = scraper.get_page_text_content(another_url)
    # print(content)

    # Close the browser after all operations are done
    scraper.close()
