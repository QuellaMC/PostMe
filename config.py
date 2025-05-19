import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- OpenAI Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)
MODEL_ID = "gpt-4o-2024-08-06"  # Model for content generation
REVIEW_MODEL_ID = "gpt-4o-2024-08-06" # Model for AI review

# --- Language & Region Configuration ---
# Languages can be ISO 639-1 codes (e.g., 'en', 'zh', 'es')
# Countries can be ISO 3166-1 alpha-2 codes (e.g., 'US', 'CN', 'GB')
INSTAGRAM_LANGUAGE = "en"
INSTAGRAM_COUNTRY = "US" # Currently not used
REDNOTE_LANGUAGE = "zh"
REDNOTE_COUNTRY = "CN" # Currently not used
NEWS_FETCH_LANGUAGE = "en" # Language for fetching news articles
NEWS_FETCH_COUNTRY = "US"  # Country for fetching news articles

# --- Prompt Configuration ---
INSTAGRAM_PROMPT_FILE = "prompts/instagram_prompt.json"
REDNOTE_PROMPT_FILE = "prompts/rednote_prompt.json"

# --- Output Configuration ---
OUTPUT_DIR = "generated_posts"

# --- Review Configuration ---
# Control AI review for each step
AI_REVIEW_ENABLED_NEWS = True       # Enable/disable AI review for the combined news summary
AI_REVIEW_ENABLED_POST_TEXT = True  # Enable/disable AI review for the generated post text
AI_REVIEW_ENABLED_IMAGE_PROMPT = True # Enable/disable AI review for the generated image prompt

# Control *Human* review requirements (works alongside AI review flags)
HUMAN_REVIEW_REQUIRED_NEWS = False # Default to AI review only for news (if AI_REVIEW_ENABLED_NEWS is True)
HUMAN_REVIEW_REQUIRED_POST = True # Default to require human review for final post (even if AI approved or AI review was skipped)
MAX_REGENERATION_ATTEMPTS = 1 # Max times to try regenerating content after rejection
AD_CONTENT_INTENSITY_PERCENT = 20 # Target percentage for advertising content (0-100). Influences prompt instructions.

# --- News Fetcher Configuration ---
NEWS_KEYWORDS = ["ecommerce"] # Default keywords
NEWS_MAX_ARTICLES = 3 # Max articles to fetch *initially* (before filtering used ones)
USED_ARTICLES_FILE_PATH = "used_articles.json" # File to store links of used articles

# --- Validation ---
def validate_config():
    """Basic validation to ensure critical configs are set."""
    if not OPENAI_API_KEY:
        raise ValueError("Configuration Error: OPENAI_API_KEY not found in environment or .env file.")
    # Add more checks as needed (e.g., file existence)
    print("[INFO] Configuration loaded and validated.")

# Ensure output directory exists when config is loaded
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Threshold for article length (in characters) above which summarization will be attempted.
# Adjust this value as needed.
ARTICLE_SUMMARIZATION_THRESHOLD = 1500 
NEWS_FETCH_INITIAL_BATCH_SIZE = 20

# --- Scheduler Configuration ---
SCHEDULE_DAY = "monday" # Day of the week for scheduled runs (e.g., "monday", "tuesday")
SCHEDULE_TIME = "09:00" # Time for scheduled runs (HH:MM format)