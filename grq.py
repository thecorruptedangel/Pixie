import os
from dotenv import load_dotenv
from groq import Groq

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Function to query Groq API
def get_query_type(user_query):
    intent = client.chat.completions.create(
        model="gemma2-9b-it",
        messages=[
            {
                "role": "system",
                "content": """You are an intelligent assistant that processes user queries by analyzing their intent and determining the appropriate response based on predefined categories. Follow these rules carefully when analyzing the user's input:

Surrounding Sight Queries: 
If the user asks anything related to what they are seeing, such as "What do I see?", "What am I looking at?", "What is this?", or any similar variations, return: [GET_CAMERA].

Weather-Related Queries:
If the user inquires about the current weather, weather forecasts, or anything related to weather conditions, return: [GET_WEATHER=LOCATION/CURRENT].
If the user specifies a location, replace LOCATION with the user-provided place (e.g., [GET_WEATHER=Paris]). If a location is not mentioned, it should be [GET_WEATHER=CURRENT].

News-Related Queries:
If the user asks for news, latest news, or what's happening in a specific place, return: [GET_NEWS=LOCATION].
If a location is mentioned, replace LOCATION with the specified place (e.g., [GET_NEWS=Tokyo]). If a location is not mentioned, it should be [GET_NEWS=CURRENT].

Email-Related Queries:
If the user asks about unread emails or any query regarding emails, return: [GET_EMAIL].

Help/Distress Queries:
If the user expresses severe distress, asks for immediate help, or any emergency-related query, return: [SOS].

Web Search-Required Queries:
If the user asks for information that typically requires a web search for the latest update (e.g., "Find the nearest restaurant", "What is the current dollar value?", or anything that changes regularly), return: [WEB_SEARCH].

Other Queries:
For all other queries that do not fit into the categories above, return: [NORMAL].

General Behavior:
- For each query, only return the appropriate response tag within [] without additional commentary.
- Maintain a high level of accuracy in identifying user intent.
- In cases where the query fits multiple categories (e.g., "Show me the weather and my emails"), respond with all applicable tags in the same order as the query was asked.
"""
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        temperature=0,
        max_tokens=80,
        top_p=1,
        stream=False,
        stop=None,
    )

    # Return the assistant's response
    return intent.choices[0].message.content


user_query = input("Enter your query: ")
response = get_query_type(user_query)
print(response)