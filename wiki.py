import wikipedia
import re
import warnings
from bs4 import GuessedAtParserWarning

def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', text)).strip()

def safe_wikipedia_page(title):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=GuessedAtParserWarning)
        return wikipedia.page(title)

def search_wikipedia():
    query = input("Enter your search query: ")
    
    try:
        search_results = wikipedia.search(query)
        
        if not search_results:
            print("No results found for your query.")
            return
        
        for i, result in enumerate(search_results[:5], 1):
            try:
                page = safe_wikipedia_page(result)
                summary = clean_text(page.summary)
                print(f"{summary[:300]}...")  # Print first 300 characters

            except (wikipedia.DisambiguationError, wikipedia.PageError):
                continue
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    search_wikipedia()