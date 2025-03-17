import os
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
# Load API key from .env file
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

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


# Function to query Groq API
def get_weather(user_query):
    intent = client.chat.completions.create(
        model="gemma2-9b-it",
        messages=[
            {
                "role": "system",
                "content": """You are an expert weather assistant tasked with extracting weather data from unstructured web-scraped text. Your goal is to accurately identify current weather conditions and forecasts, specifically focusing on temperature, precipitation, humidity, wind speed, and weather trends. If information is missing, respond with `[NO_INFO]`.

**Instructions**:

1. **Current Weather**:
   - Extract and report: temperature, precipitation %, humidity, wind speed, and overall weather condition (e.g., mist, rain).
   - Predict if it will rain today based on the data (precipitation %, condition). If uncertain, use related indicators.

2. **Forecast**:
   - Extract forecasts for upcoming days, including: high/low temperatures, precipitation %, and weather condition (e.g., scattered showers).
   - Identify weather trends (e.g., warming, cooling, rain likelihood).

3. **Handle Missing Data**:
   - If any required weather data is missing, respond with `[NO_INFO]`.

4. NO NEED TO ADD ANY FURTHER EXPLANATIONS. STRICTLY STICK TO THE FOLLOWING OUTPUT FORMAT

5. **Output Format**:
   ```
   - Condition: [condition]
   - Temp: [temp]°C
   - Precipitation: [precipitation]%
   - Humidity: [humidity]%
   - Wind: [wind]
   - Rain Today: [Yes/No]

   Forecast:
   Day 1: [condition], High: [temp]°C, Low: [temp]°C
   Day 2: [condition], High: [temp]°C, Low: [temp]°C
   ```
"""
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        temperature=0,
        max_tokens=500,
        top_p=1,
        stream=False,
        stop=None,
    )

    # Return the assistant's response
    return intent.choices[0].message.content

# Example usage
if __name__ == "__main__":
    scraper = PlaywrightWebKitScraper()
    print("Loaded")
    LOCATION = input("Enter your location: ")

    url = f"https://www.google.com/search?q=weather+in+{LOCATION}&sourceid=chrome&ie=UTF-8"  # Replace with your target URL
    content = scraper.get_page_text_content(url)
    response = get_weather(content)
  

    print(response)



