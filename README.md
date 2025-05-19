# AI Social Media Post Generator

## Overview

This program automates the generation of social media posts (specifically for Instagram and Rednote/Xiaohongshu) based on recent e-commerce news relevant to small businesses, creators, and vendors. It fetches news, summarizes articles, generates post text and image prompts using OpenAI's GPT models, reviews the content (using AI and optional human input), generates images using DALL-E 3, and saves the final approved posts along with their images.

## Features

*   **Multi-Platform Support:** Generates content tailored for Instagram and Rednote.
*   **News-Driven Content:** Fetches recent news articles relevant to e-commerce using Google News RSS.
*   **Article Summarization:** Summarizes long news articles using an LLM before feeding them into the post generation prompt.
*   **AI Content Generation:** Utilizes OpenAI's GPT models (configurable) to generate post text, hashtags, and image prompts based on news insights and platform-specific prompts.
*   **Context Injection:** Injects Airmart brand context and configurable ad intensity instructions into the generation prompts.
*   **AI Content Review:** Employs an AI model to review generated content against predefined criteria (relevance, brand voice, clarity, platform fit).
*   **Human Review Workflow:** Includes an optional but configurable step for human review and feedback via the console.
*   **Targeted Regeneration:** If content is rejected, the system attempts to regenerate only the rejected parts (text or image prompt) based on feedback.
*   **Image Generation:** Generates images using DALL-E 3 based on the approved image prompts.
*   **Persistent Storage:** Saves approved posts (text, hashtags, image prompt, image path) to JSON files and downloaded images to a local directory.
*   **Duplicate Prevention:** Keeps track of used news article links to avoid reprocessing the same news.
*   **Configuration:** Easily configurable via `.env` and `config.py` files (API keys, models, languages, review settings, etc.).
*   **Scheduling:** Can run the workflow on a predefined schedule (e.g., weekly).
*   **Modular Design:** Code is structured into logical modules (AI services, storage, workflow, etc.).

## Architecture

The program follows a modular architecture:

1.  **`main.py`**: The entry point. Initializes services, the workflow, and the scheduler. Runs the workflow once immediately and then starts the schedule.
2.  **`scheduler.py`**: Uses the `schedule` library to run the workflow periodically based on settings in `config.py`.
3.  **`workflow.py` (`ContentWorkflow` class)**: Orchestrates the entire process:
    *   Loads used article history (`storage.py`).
    *   Fetches news (`news_fetcher.py`).
    *   Summarizes articles if needed (`ai_services.py` -> `summarizer_agent.py`).
    *   Reviews the combined news summary (`ai_services.py`, `reviewers.py`).
    *   If news is approved, loops through configured platforms (Instagram, Rednote):
        *   Loads platform-specific prompts (`utils.py`).
        *   Loads Airmart context (`utils.py`).
        *   Generates ad intensity instructions (`workflow.py`).
        *   Generates post content (text, image prompt, hashtags) (`ai_services.py`).
        *   Reviews generated content (`ai_services.py`, `reviewers.py`).
        *   Handles regeneration attempts based on review feedback.
        *   If post is approved, generates image (`ai_services.py`).
        *   Saves approved content and image (`storage.py`).
    *   Saves used article links for approved news (`storage.py`).
4.  **`news_fetcher.py`**: Fetches news articles from Google News RSS, decodes links, fetches full article text using `newspaper3k`, and filters based on keywords and used links.
5.  **`ai_services.py` (`AIService` class)**: Interacts with the OpenAI API for:
    *   Content generation (`generate_content`).
    *   Content review (`review_content`).
    *   Article summarization (`summarize_article_text` via `summarizer_agent.py`).
    *   Image generation (`generate_image`).
6.  **`summarizer_agent.py`**: Contains the logic to call the LLM specifically for summarizing text.
7.  **`reviewers.py` (`ConsoleReviewer` class)**: Handles the human review part of the workflow, prompting for approval/feedback via the console. (Could be swapped for other review implementations).
8.  **`storage.py` (`FileStorage` class)**: Handles:
    *   Saving generated post data (JSON).
    *   Downloading and saving generated images.
    *   Loading and appending used article links (`used_article_links.txt`).
9.  **`utils.py`**: Contains helper functions for loading prompts and context from files.
10. **`config.py`**: Loads configuration from environment variables (`.env`) and defines application settings (API keys, models, languages, prompts, directories, review flags, thresholds, schedule).
11. **`.env`**: Stores sensitive information like API keys (should NOT be committed to version control).
12. **`requirements.txt`**: Lists Python package dependencies.
13. **`prompts/`**: Directory containing JSON files for base prompts and brand context.

## Setup

1.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create `.env` file:**
    *   Copy or rename `.env.example` (if provided) to `.env`.
    *   Edit the `.env` file and add your OpenAI API key and optionally the base URL if using a proxy:
        ```dotenv
        # .env file
        OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        OPENAI_BASE_URL="https://your-proxy-url/v1" # Optional: remove if using default OpenAI endpoint
        ```
4.  **Configure `config.py`:**
    *   Review settings in `config.py`, especially:
        *   `MODEL_ID`, `REVIEW_MODEL_ID`: Ensure these match models accessible via your API key/endpoint.
        *   Language/Country settings (`INSTAGRAM_LANGUAGE`, `REDNOTE_LANGUAGE`, `NEWS_FETCH_LANGUAGE`, etc.).
        *   Prompt file paths (`INSTAGRAM_PROMPT_FILE`, `REDNOTE_PROMPT_FILE`).
        *   Review flags (`AI_REVIEW_ENABLED_*`, `HUMAN_REVIEW_REQUIRED_*`).
        *   `AD_CONTENT_INTENSITY_PERCENT`.
        *   `NEWS_KEYWORDS`.
        *   `SCHEDULE_DAY`, `SCHEDULE_TIME`.
5.  **Ensure Prompt Files Exist and are Correct:**
    *   Check that the prompt files specified in `config.py` (e.g., `prompts/instagram_prompt.json`, `prompts/rednote_prompt.json`) exist and are formatted correctly (see `utils.py` for expected format).
    *   Check that the `prompts/airmart_context.json` file exists and is formatted correctly.
    *   If prompts reference external content files (`content_file`), ensure those files exist in the same directory as the main prompt JSON.

## Configuration

Configuration is managed through two main files:

*   **`.env`**:
    *   `OPENAI_API_KEY`: **Required**. Your secret API key for OpenAI.
    *   `OPENAI_BASE_URL`: Optional. Use if you access the OpenAI API through a proxy or alternative endpoint.
*   **`config.py`**:
    *   **OpenAI:** `MODEL_ID`, `REVIEW_MODEL_ID`.
    *   **Language/Region:** `*_LANGUAGE`, `*_COUNTRY` settings for different platforms and news fetching.
    *   **Prompts:** `*_PROMPT_FILE` paths.
    *   **Output:** `OUTPUT_DIR` for generated posts and images.
    *   **Review:** Flags to enable/disable AI review (`AI_REVIEW_ENABLED_*`) and require human review (`HUMAN_REVIEW_REQUIRED_*`). `MAX_REGENERATION_ATTEMPTS`.
    *   **Ad Intensity:** `AD_CONTENT_INTENSITY_PERCENT` (0-100) controls how prominently Airmart is featured in the generated text.
    *   **News Fetcher:** `NEWS_KEYWORDS`, `NEWS_MAX_ARTICLES` (target number of *new* articles), `USED_ARTICLES_FILE_PATH`, `ARTICLE_SUMMARIZATION_THRESHOLD` (character count to trigger summarization), `NEWS_FETCH_INITIAL_BATCH_SIZE` (how many articles to check from RSS feed).
    *   **Scheduler:** `SCHEDULE_DAY`, `SCHEDULE_TIME`.

## Workflow Steps

The core workflow executed by `ContentWorkflow.run()` is:

1.  **Load History:** Load previously used article links from `used_article_links.txt`.
2.  **Fetch News (`_run_news_step`)**:
    *   Call `news_fetcher.get_recent_ecommerce_news` with keywords, language/country settings, max articles desired, and the set of used links.
    *   Process fetched articles:
        *   Summarize content if it exceeds `ARTICLE_SUMMARIZATION_THRESHOLD` (`ai_service.summarize_article_text`).
        *   Combine processed article content into a single `news_summary`.
    *   Review `news_summary`:
        *   AI Review (if `AI_REVIEW_ENABLED_NEWS` is True).
        *   Human Review (if AI rejected or `HUMAN_REVIEW_REQUIRED_NEWS` is True).
    *   If rejected, halt workflow. If no new news, halt workflow.
    *   If approved, store the summary and the list of links corresponding to the articles *used* in the summary.
3.  **Platform Loop (Instagram, Rednote)**:
    *   For each platform defined in `platform_configs`:
        *   **Attempt Loop (Generation & Review)**: Loop up to `max_regen_attempts + 1` times.
            *   **Generate Content (`_run_generation_step`)**:
                *   Load base prompt messages (`utils.load_prompt_from_file`).
                *   Load Airmart context (`utils.load_airmart_context`).
                *   Generate ad intensity instruction (`_generate_ad_intensity_instruction`).
                *   Inject context, intensity instruction, news summary, language, and any regeneration feedback into the prompt messages.
                *   Call `ai_service.generate_content` (handles API call and JSON parsing).
            *   If generation fails, retry if attempts remain.
            *   **Review Content (`_run_review_step`)**:
                *   AI Review (if `AI_REVIEW_ENABLED_POST_TEXT` / `AI_REVIEW_ENABLED_IMAGE_PROMPT` are True). Reviews text and image prompt separately.
                *   Human Review (`ConsoleReviewer`) (if any AI component rejected or `HUMAN_REVIEW_REQUIRED_POST` is True). Prompts user for approval/feedback for text and image prompt.
            *   If approved, break the attempt loop for this platform. Store the approved content.
            *   If rejected, prepare feedback for the next attempt (targeted regeneration). If max attempts reached, mark as failed.
        *   **Post-Approval Processing**:
            *   If content for the platform was approved:
                *   Generate image using `ai_service.generate_image` with the approved image prompt.
                *   Save content (JSON) and downloaded image using `storage.save_content`. Mark `any_post_saved` as True.
4.  **Save History**: If any post was successfully saved (`any_post_saved` is True), append the links from the approved news summary to `used_article_links.txt`.
5.  **Report**: Print final status (Full Success, Partial Success, No content approved/saved).

## Modules

*   **`main.py`**: Entry point, initialization, runs scheduler.
*   **`config.py`**: Configuration settings and validation.
*   **`workflow.py`**: Orchestrates the main content generation logic.
*   **`scheduler.py`**: Handles scheduling of the workflow runs.
*   **`ai_services.py`**: Interface with OpenAI API for generation, review, summarization, image creation.
*   **`summarizer_agent.py`**: Specific LLM call logic for text summarization.
*   **`news_fetcher.py`**: Fetches and processes news articles from Google News RSS.
*   **`reviewers.py`**: Handles the human review interaction (currently via console).
*   **`storage.py`**: Manages saving posts/images and tracking used article links.
*   **`utils.py`**: Utility functions for loading data from files (prompts, context).

## Running the Program

1.  Ensure setup is complete (dependencies installed, `.env` created, `config.py` reviewed).
2.  Activate the virtual environment (if used).
3.  Run the main script:
    ```bash
    python main.py
    ```

The program will:

*   Perform an initial run of the workflow immediately.
*   Print logs to the console indicating progress, warnings, and errors.
*   Prompt for human review in the console if configured.
*   Save generated content and images to the directory specified in `config.OUTPUT_DIR` (default: `generated_posts`).
*   Save used article links to `used_article_links.txt` within the output directory.
*   After the initial run, it will start the scheduler and wait for the next scheduled run (e.g., every Monday at 9:00 AM). Press `Ctrl+C` to stop the scheduler.

## Error Handling

*   **Configuration Errors:** `config.validate_config()` checks for essential settings (like API key) on startup. `main.py` catches `ValueError` during config validation and exits.
*   **Import Errors:** Caught in `main.py` to provide helpful messages.
*   **API Errors:** `ai_services.py` catches specific `openai` exceptions (e.g., `AuthenticationError`, `RateLimitError`, `APIError`, `BadRequestError`) and returns error messages/None, logging details. `summarizer_agent.py` also handles `OpenAIError`.
*   **News Fetching Errors:** `news_fetcher.py` handles `feedparser` errors, `ArticleException` from `newspaper3k`, and returns error strings or empty lists.
*   **File I/O Errors:** `storage.py` and `utils.py` handle `FileNotFoundError` and other potential exceptions during file reading/writing, logging warnings/errors.
*   **JSON Errors:** Errors during JSON parsing (in prompts, context, or LLM responses) are caught and logged.
*   **Workflow Errors:** The main `run` method in `ContentWorkflow` has a broad `try...except` block to catch unexpected errors during the workflow execution, log them, and attempt to save any collected used links before exiting. The scheduler's `_job` method also has a broad exception handler.
*   **Logging:** The application uses `print` statements prefixed with `[INFO]`, `[WARN]`, `[ERROR]`, `[DEBUG]` (some commented out), or specific step markers like `[WORKFLOW]` for logging progress and issues to the console. Tracebacks are printed for critical errors. 