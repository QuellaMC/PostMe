import os
import feedparser # Use feedparser for RSS
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus # For URL encoding keywords
from googlenewsdecoder import gnewsdecoder
from newspaper import Article, ArticleException # Added for fetching full article text
from typing import List, Dict, Union, Set # Add Set typing import

import config # Import config to get batch size

# Removed config and summarizer imports

# Load environment variables from .env file (primarily for OPENAI_API_KEY now)
load_dotenv()

# --- Configuration ---
# Base URL structure for Google News RSS Search
GOOGLE_NEWS_RSS_URL_TEMPLATE = "https://news.google.com/rss/search?pz=1&cf=all&q={query}&hl={lang}&gl={country}&ceid={country}:{lang}"
# Default country for search (adjust if needed)
DEFAULT_COUNTRY = "US"

# --- Tool Schema Definition for OpenAI Function Calling ---
# (The schema remains the same as it defines the interface for the LLM)
# tools = [
#     {
#         "type": "function",
#         "function": {
#             "name": "get_recent_ecommerce_news",
#             "description": "Fetches recent news articles relevant to small food businesses, independent creators, pop-up vendors, and farmers market sellers using Google News RSS. Decodes the Google News link, fetches the full article text, filters out previously used links, and returns the content of the requested number of articles.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "query_keywords": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "description": "List of specific keywords or phrases to search for (e.g., ['online bakery marketing', 'food vendor regulations', 'Rednote commerce trends']). Prioritize terms relevant to small food/creator businesses.",
#                     },
#                     "excluded_keywords": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "description": "Optional list of keywords or phrases to exclude. Note: Direct exclusion is less effective with RSS; results containing these may still appear but can be filtered post-fetch.",
#                     },
#                     "target_language": {
#                         "type": "string",
#                         "description": "Optional preferred language code (e.g., 'en', 'zh-CN', 'zh-TW'). Determines the 'hl' parameter.",
#                         "default": "en"
#                     },
#                     "target_country": {
#                          "type": "string",
#                          "description": "Optional country code (e.g., 'US', 'CN', 'GB') to target the search. Determines the 'gl' and 'ceid' parameters.",
#                          "default": "US"
#                     },
#                     "max_articles": {
#                         "type": "integer",
#                         "description": "Maximum number of *new*, valid articles to find and return.",
#                         "default": 3
#                     }
#                 },
#                 "required": ["query_keywords"],
#             },
#         },
#     }
# ]

# --- News Fetching Function Implementation (Using feedparser) ---

def get_recent_ecommerce_news(query_keywords: list,
                              excluded_keywords: list = None,
                              target_language: str = 'en',
                              target_country: str = DEFAULT_COUNTRY,
                              max_articles: int = 3,
                              used_links: Set[str] = set(), # Add param for used links
                              initial_fetch_count: int = getattr(config, 'NEWS_FETCH_INITIAL_BATCH_SIZE', 20) # Use getattr for safety
                              ) -> Union[List[Dict[str, str]], str]:
    """
    Fetches recent e-commerce news articles from Google News RSS based on keywords,
    decodes the URL, attempts to fetch the full article text, filters out used links,
    and returns up to max_articles.

    Args:
        query_keywords (list): List of keywords/phrases to search for.
        excluded_keywords (list, optional): List of keywords/phrases to attempt to filter out post-fetch.
        target_language (str, optional): Preferred language code (e.g., 'en', 'zh-CN').
        target_country (str, optional): Country code (e.g., 'US', 'CN').
        max_articles (int, optional): Max number of valid, unused articles to return.
        used_links (Set[str], optional): A set of URLs that have already been processed and should be skipped.
        initial_fetch_count (int, optional): How many articles to initially pull from the RSS feed.

    Returns:
        Union[List[Dict[str, str]], str]: A list of dictionaries, where each dict contains
            'title', 'link', 'date', and 'content' for a fetched article.
            Returns an error string if fetching/parsing fails.
            Returns an empty list if no valid, unused articles are found.
    """
    print("[INFO] Attempting to fetch Google News RSS...")
    print(f"[INFO]   Keywords: {query_keywords}")
    print(f"[INFO]   Language: {target_language}, Country: {target_country}")
    print(f"[INFO]   Initial Batch Size: {initial_fetch_count}, Max New Articles: {max_articles}, Used Links Provided: {len(used_links)}")

    if not query_keywords:
        print("[ERROR] get_recent_ecommerce_news called without query keywords.")
        return "Error: No query keywords provided."

    # Format query string for URL (e.g., join with " OR ", URL encode)
    query_formatted = " ".join(f'"{phrase}"' if " " in phrase else phrase for phrase in query_keywords)
    query_encoded = quote_plus(query_formatted)

    # Construct the final URL
    rss_url = GOOGLE_NEWS_RSS_URL_TEMPLATE.format(
        query=query_encoded,
        lang=target_language,
        country=target_country
    )
    print(f"[INFO] Fetching from URL: {rss_url}")

    try:
        # Parse the RSS feed
        print("[INFO] Parsing RSS feed...")
        feed_data = feedparser.parse(rss_url)

        # Check for basic feed errors
        if feed_data.bozo:
            bozo_exception = feed_data.get('bozo_exception', 'Unknown parsing error')
            print(f"[ERROR] Error parsing RSS feed: {bozo_exception}")
            if isinstance(bozo_exception, feedparser.CharacterEncodingOverride):
                 return f"Error: Feed character encoding issue: {bozo_exception}"
            elif isinstance(bozo_exception, Exception):
                 return f"Error: Could not fetch or parse feed: {bozo_exception}"
            else:
                 return f"Error: Malformed RSS feed encountered: {bozo_exception}"

        if not feed_data.entries:
            print("[INFO] Feed parsed successfully, but no news entries found for the query.")
            return []

        # Extract article data, applying post-fetch exclusion filter
        articles = []
        feed_entries_to_consider = feed_data.entries[:initial_fetch_count] # Use configured batch size

        print(f"[INFO] Processing up to {len(feed_entries_to_consider)} entries from feed to find {max_articles} valid, new articles...")

        for entry_idx, entry in enumerate(feed_entries_to_consider):
            if len(articles) >= max_articles:
                print(f"[INFO] Collected the desired number of new articles ({max_articles}). Stopping further processing.")
                break
            # Add index for clearer logging
            print(f"[DEBUG] Processing feed entry {entry_idx+1}/{len(feed_entries_to_consider)}...")

            title = entry.get('title', 'No Title')
            rss_summary = entry.get('summary', entry.get('description', 'No summary available'))
            google_news_link = entry.get('link', '#')
            pub_date_str = entry.get('published', '')
            article_text = "[Full text not fetched]"
            final_link = google_news_link # Use Google link as fallback initially

            if not title or not rss_summary or title == '[Removed]':
                 print(f"[DEBUG]   Skipping entry {entry_idx+1} due to missing title/summary or '[Removed]' title: '{title}'")
                 continue

            # --- Attempt to Decode URL early to check against used_links --- 
            temp_final_link = google_news_link
            decoded_url_for_check = None # Store the successfully decoded URL here
            if google_news_link and google_news_link != '#':
                try:
                    print(f"[DEBUG]   Attempting to decode Google News link: {google_news_link}")
                    decoded_info = gnewsdecoder(google_news_link)
                    if decoded_info and decoded_info.get("status") and decoded_info.get("decoded_url"):
                        decoded_url_for_check = decoded_info["decoded_url"]
                        temp_final_link = decoded_url_for_check # Update potential final link
                        print(f"[DEBUG]   Decoded URL for used check: {temp_final_link}")
                    else:
                         print(f"[DEBUG]   Decoding failed or returned invalid status for: {google_news_link}")
                    # If decoding fails, temp_final_link remains the google_news_link
                except Exception as e:
                    print(f"[WARN]   Error during URL decoding for used check (will proceed with original link): {e}")
            
            # --- Filter based on USED LINKS (check both decoded and original link) --- 
            if temp_final_link in used_links or (google_news_link != temp_final_link and google_news_link in used_links):
                 print(f"[INFO]   Skipping article (already used): '{title}' - Link: {temp_final_link} (or original {google_news_link})")
                 continue
            # --- END USED LINKS FILTER --- 

            # Post-fetch filtering for excluded keywords
            if excluded_keywords:
                excluded = False
                for keyword in excluded_keywords:
                    if keyword.lower() in title.lower() or keyword.lower() in rss_summary.lower():
                        excluded = True
                        print(f"[INFO]   Skipping article due to excluded keyword '{keyword}' in title/RSS summary: '{title}'")
                        break
                if excluded:
                    continue

            # --- Fetch Full Text (using the decoded URL if available) ---
            final_link = temp_final_link # Set the final link based on successful decode or original
            if decoded_url_for_check: # Use the successfully decoded URL for fetching
                print(f"[INFO]   Attempting to fetch full text from decoded URL: {final_link}")
                try:
                    article = Article(final_link)
                    article.download()
                    article.parse()
                    fetched_text = article.text

                    if fetched_text:
                        print(f"[INFO]   Successfully fetched full text ({len(fetched_text)} chars) for: '{title}'")
                        article_text = fetched_text
                    else:
                        article_text = "[Full text fetched but empty]"
                        print(f"[WARN]   Fetched empty text for: '{title}' ({final_link})")

                except ArticleException as e:
                    article_text = f"[Error fetching/parsing article: {e}]"
                    print(f"[WARN]   Newspaper3k error fetching/parsing '{title}' ({final_link}): {e}")
                except Exception as e:
                    article_text = f"[Unexpected error fetching article: {e}]"
                    print(f"[WARN]   Unexpected Newspaper3k error for '{title}' ({final_link}): {e}")
            elif google_news_link and google_news_link != '#': # Decoding failed or wasn't applicable
                article_text = "[Could not decode Google News URL, unable to fetch full text]"
                print(f"[WARN]   Could not decode Google News URL for '{title}', cannot fetch full text directly.")
            else:
                 article_text = "[Invalid Google News link provided]"
                 print(f"[WARN]   Invalid Google News link for entry {entry_idx+1}. Title: '{title}'")

            # Fallback to RSS summary
            if article_text.startswith("[") and rss_summary:
                print(f"[INFO]   Falling back to RSS summary for: '{title}'")
                article_text = f"[Using RSS Summary]: {rss_summary}"

            # Check final content validity
            is_error_content = article_text.startswith(("[Error", "[Unexpected error", "[Invalid Google", "[URL decoding failed", "[Could not decode"))
            is_empty_content = article_text in ["[Full text not fetched]", "[Full text fetched but empty]"]
            is_fallback_content = article_text.startswith("[Using RSS Summary]")

            if (not is_error_content and not is_empty_content) or is_fallback_content:
                article_data = {
                    'title': title,
                    'link': final_link, # Store the link (decoded if possible)
                    'date': pub_date_str,
                    'content': article_text
                }
                articles.append(article_data)
                print(f"[INFO]   Successfully processed and added NEW article: '{title}' (Total collected: {len(articles)})")
            else:
                 print(f"[WARN]   Skipping article '{title}' due to fetching/processing failure or empty content. Status: {article_text[:100]}...")

        if not articles:
             print("[WARN] Found feed entries, but couldn't extract valid *new* content or all were excluded/filtered.")
             return []
        elif len(articles) < max_articles:
            print(f"[WARN] Only collected {len(articles)} valid new articles, less than the requested {max_articles}.")

        print(f"[INFO] Successfully processed and collected {len(articles)} new news items.")
        return articles

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during Google News RSS fetching: {e}")
        import traceback
        traceback.print_exc()
        return f"An unexpected error occurred: {e}"

# --- Example Usage (for testing) ---
if __name__ == "__main__":
    print("[TEST] === Testing get_recent_ecommerce_news function ===")
    # Example keywords
    test_keywords = ["ecommerce"]
    # Simulate some used links
    mock_used_links = {"https://www.example.com/used-article1", "https://www.example.com/used-article2"}
    # Test with max_articles=2 and passing used_links
    news_result = get_recent_ecommerce_news(query_keywords=test_keywords, target_language='en', target_country='US', max_articles=2, used_links=mock_used_links)
    print("\n[TEST] --- News Result (en, US, max=2) ---")
    if isinstance(news_result, str):
        print(f"[TEST] Error: {news_result}")
    elif isinstance(news_result, list):
        if not news_result:
            print("[TEST] No *new* articles found.")
        else:
            print(f"[TEST] Fetched {len(news_result)} new articles:")
            for i, article in enumerate(news_result):
                print(f"\n[TEST] Article {i+1}:")
                print(f"[TEST]   Title: {article.get('title')}")
                print(f"[TEST]   Link: {article.get('link')}")
                print(f"[TEST]   Date: {article.get('date')}")
                content_preview = article.get('content', '')[:150] + ('...' if len(article.get('content', '')) > 150 else '')
                print(f"[TEST]   Content Preview: {content_preview}")
    else:
        print(f"[TEST] Unexpected result type: {type(news_result)}")
    print("[TEST] --------------------------------------\n")

    # # Test Chinese language search (example)
    # print("Testing Chinese language search...")
    # test_keywords_zh = ["小型企业", "电子商务趋势"] # "small business", "e-commerce trends"
    # news_result_zh = get_recent_ecommerce_news(query_keywords=test_keywords_zh, target_language='zh-CN', target_country='CN', max_articles=1)
    # print("\n--- Chinese News Result ---")
    # print(news_result_zh)
    # print("-------------------------\n")

    # # Test exclusion (may not be very effective)
    # print("Testing exclusion...")
    # test_keywords_exclude = ["retail marketing"]
    # test_excluded = ["Amazon"]
    # news_result_exclude = get_recent_ecommerce_news(query_keywords=test_keywords_exclude, excluded_keywords=test_excluded, max_articles=1)
    # print("\n--- Exclusion Test Result ---")
    # print(news_result_exclude)
    # print("---------------------------\n")

    # # Test with unlikely keywords
    # print("Testing with unlikely keywords...")
    # test_keywords_no_results = ["asdfqwerzxcv", "qwertyuiopasdfghjkl"]
    # news_result_no_results = get_recent_ecommerce_news(query_keywords=test_keywords_no_results)
    # print("\n--- No Results Test ---")
    # if isinstance(news_result_no_results, str):
    #     print(f"Error: {news_result_no_results}")
    # elif isinstance(news_result_no_results, list) and not news_result_no_results:
    #     print("Correctly returned no articles (empty list).")
    # else:
    #     print(f"Unexpected result for no results test: {news_result_no_results}")
    # print("----------------------\n")

    print("[TEST] === News Fetcher Testing Complete ===")
