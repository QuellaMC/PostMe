import time
import traceback
import os
from typing import Dict, Any, Optional, Callable, List, Union, Set

# Configuration and Utilities
import config
from config import (
    ARTICLE_SUMMARIZATION_THRESHOLD,
    INSTAGRAM_LANGUAGE,
    INSTAGRAM_COUNTRY, # Keep country in case needed later
    REDNOTE_LANGUAGE,
    REDNOTE_COUNTRY,   # Keep country in case needed later
    NEWS_FETCH_LANGUAGE,
    NEWS_FETCH_COUNTRY,
    NEWS_KEYWORDS
)
from utils import load_prompt_from_file, load_airmart_context

# Services
from ai_services import AIService
from reviewers import ConsoleReviewer # Can be swapped for other reviewer implementations
from storage import FileStorage

# News Fetcher (handle import gracefully)
try:
    # Assuming news_fetcher.py exists and has this function
    from news_fetcher import get_recent_ecommerce_news
except ImportError:
    print("[WARN] news_fetcher.py not found or get_recent_ecommerce_news missing. Using dummy news function for workflow.")
    def get_recent_ecommerce_news(*args, **kwargs) -> Union[List[Dict[str, str]], str]:
        print("[WARN] Using dummy news fetcher function in workflow!")
        return [{'title': 'Dummy News', 'link': '#dummy', 'date':'', 'content':'Dummy News: E-commerce sales are booming this week.'}]

class ContentWorkflow:
    """Orchestrates the multi-step content generation workflow."""

    def __init__(self,
                 ai_service: AIService,
                 reviewer: ConsoleReviewer, # Or a more generic Reviewer interface
                 storage: FileStorage,
                 news_fetcher_func: Callable[..., Union[List[Dict[str, str]], str]] = get_recent_ecommerce_news,
                 max_regen_attempts: int = config.MAX_REGENERATION_ATTEMPTS,
                 human_review_required_news: bool = config.HUMAN_REVIEW_REQUIRED_NEWS,
                 human_review_required_post: bool = config.HUMAN_REVIEW_REQUIRED_POST,
                 max_news_articles: int = getattr(config, 'MAX_NEWS_ARTICLES_TO_PROCESS', 3)
                 ):
        self.ai_service = ai_service
        self.reviewer = reviewer
        self.storage = storage
        self.news_fetcher_func = news_fetcher_func
        self.max_regen_attempts = max_regen_attempts
        self.human_review_required_news = human_review_required_news
        self.human_review_required_post = human_review_required_post
        self.max_news_articles = max_news_articles
        print(f"[INFO] ContentWorkflow initialized.")
        print(f"[INFO]   Max News Articles to Process: {self.max_news_articles}")
        print(f"[INFO]   Max Regeneration Attempts: {self.max_regen_attempts}")
        print(f"[INFO]   Human Review Required (News): {self.human_review_required_news}")
        print(f"[INFO]   Human Review Required (Post): {self.human_review_required_post}")

    # --------------------------------------------------------------------------
    # Private Helper Methods for Workflow Steps
    # --------------------------------------------------------------------------

    def _run_news_step(self, used_links: Set[str]) -> Dict[str, Any]:
        """Fetches news, processes articles, runs reviews.
           Uses language/country settings from config.
        """
        print("\n[WORKFLOW] --- Step: Fetching & Reviewing News --- ")
        # Use language/country from config
        news_lang = config.NEWS_FETCH_LANGUAGE
        news_country = config.NEWS_FETCH_COUNTRY
        print(f"[INFO]   Using News Settings: Lang={news_lang}, Country={news_country}")
        step_result = {'status': 'rejected', 'news_summary': None, 'fetched_articles': [], 'feedback': 'Unknown error'}
        try:
            keywords = NEWS_KEYWORDS
            print(f"[INFO]   Calling news fetcher with keywords: {keywords}...")
            # News fetcher handles its own internal logging
            fetched_data = self.news_fetcher_func(
                query_keywords=keywords,
                target_language=news_lang,
                target_country=news_country,
                max_articles=self.max_news_articles,
                used_links=used_links
            )

            if isinstance(fetched_data, str): # Error message returned
                 step_result['feedback'] = f"News fetching failed: {fetched_data}"
                 print(f"[ERROR]  {step_result['feedback']}")
                 return step_result
            if not fetched_data:
                 step_result['feedback'] = "News fetching succeeded, but no *new* relevant articles were found."
                 print(f"[INFO]   {step_result['feedback']}")
                 step_result['status'] = 'no_news' # Use a distinct status
                 return step_result

            step_result['fetched_articles'] = fetched_data # Store full article dicts initially
            print(f"[INFO]   Fetched {len(fetched_data)} new articles.")

            combined_news_content = ""
            processed_articles_count = 0
            links_to_add_to_used: List[str] = [] # Store links of ARTICLES ACTUALLY USED in summary
            for i, article in enumerate(fetched_data):
                print(f"[INFO]     Processing article {i+1}/{len(fetched_data)}: '{article.get('title', 'N/A')}'")
                content = article.get('content', '')
                link = article.get('link')

                if not content or content.startswith("["):
                    print(f"[WARN]     Skipping article {i+1} due to missing or placeholder content.")
                    continue

                summarized_content = content
                try:
                    if len(content) > ARTICLE_SUMMARIZATION_THRESHOLD:
                        print(f"[INFO]     Content length ({len(content)}) exceeds threshold ({ARTICLE_SUMMARIZATION_THRESHOLD}). Summarizing...")
                        # Summarizer handles its own logging now
                        summary = self.ai_service.summarize_article_text(content)
                        if summary and not summary.startswith("[Error") and not summary.startswith("[Unexpected"):
                            # print(f"[INFO]     Summarization successful. New length: {len(summary)}") # Summarizer logs success
                            summarized_content = summary
                        else:
                            print(f"[WARN]     Summarization failed or returned error. Using original content for this article. Error: {summary}")
                    else:
                        print(f"[INFO]     Content length ({len(content)}) within threshold. Skipping summarization.")
                except Exception as e:
                     print(f"[WARN]     Error during summarization check/call for article {i+1}: {e}. Using original content.")

                if combined_news_content:
                    combined_news_content += "\n\n--- ARTICLE SEPARATOR ---\n\n"
                combined_news_content += f"ARTICLE {processed_articles_count + 1}: {article.get('title', 'No Title')}\nSOURCE: {link or 'No Link'}\n\n{summarized_content}"
                processed_articles_count += 1
                # Only add link if content was successfully processed and added
                if link and link != '#':
                     links_to_add_to_used.append(link)

            if not combined_news_content:
                 step_result['feedback'] = "All fetched articles were skipped due to missing/invalid content."
                 print(f"[WARN]   {step_result['feedback']}")
                 step_result['status'] = 'rejected'
                 return step_result

            print(f"[INFO]   Combined News Content for Review (Processed {processed_articles_count} articles, Length: {len(combined_news_content)}):")
            # Fix: Assign replaced preview to variable first
            news_preview = combined_news_content[:500].replace('\n', ' ')
            print(f"[INFO]     Preview: {news_preview}...") # Shortened preview, remove newlines
            step_result['news_summary'] = combined_news_content

            # --- News Review ---
            ai_approved = True # Assume approved if AI review is skipped
            ai_review = {'approved': True, 'feedback': 'AI review skipped by config.'} # Default feedback

            if config.AI_REVIEW_ENABLED_NEWS:
                print("[INFO]   Running AI Review for News Summary...")
                # AI Service handles its own logging for the review call
                ai_review = self.ai_service.review_content(combined_news_content, 'news_summary', language=news_lang)
                ai_approved = ai_review.get('approved', False)
                print(f"[INFO]   AI Review Complete (News Approved: {ai_approved})")
            else:
                print("[INFO]   Skipping AI Review for News Summary (disabled in config).")

            step_result['feedback'] = ai_review # Store AI review feedback (or default skipped message)

            # --- Human Review Trigger ---
            if not ai_approved or self.human_review_required_news:
                print(f"[INFO]   Triggering human review for combined news (AI Approved: {ai_approved}, Human Review Required: {self.human_review_required_news})")
                # Reviewer handles its own logging
                human_review = self.reviewer.request_review(
                    content_to_review=combined_news_content,
                    content_type='news_summary',
                    ai_feedback=ai_review, # Pass AI feedback to human reviewer
                    language=news_lang
                )
                # Overwrite feedback with human review result
                step_result['feedback'] = human_review.get('feedback', {'error': 'Human review failed to return feedback.'})
                if not human_review.get('approved', False):
                    step_result['status'] = 'rejected'
                    print("[INFO]   Human rejected combined news.")
                    # Do NOT return the links if rejected by human
                    step_result['fetched_articles'] = [] # Clear the list of links
                    return step_result
                else:
                    print("[INFO]   Human approved combined news.")
                    step_result['status'] = 'approved'
                    # Return the links of the articles *used* in the approved summary
                    step_result['fetched_articles'] = links_to_add_to_used
            else:
                # If AI approved and human review not needed
                step_result['status'] = 'approved'
                print("[INFO]   AI approved combined news, skipping human review.")
                # Return the links of the articles *used* in the approved summary
                step_result['fetched_articles'] = links_to_add_to_used

            return step_result

        except Exception as e:
            print(f"[ERROR]  Critical error during news fetching/review step: {e}")
            traceback.print_exc()
            step_result['feedback'] = f'Critical error in news step: {e}'
            step_result['fetched_articles'] = [] # Ensure no links are used on critical error
            return step_result

    def _generate_ad_intensity_instruction(self) -> str:
        """Generates a prompt instruction based on the configured ad intensity percentage."""
        try:
            intensity_percent = int(config.AD_CONTENT_INTENSITY_PERCENT)
        except (ValueError, TypeError):
            print(f"[WARN] Invalid AD_CONTENT_INTENSITY_PERCENT ('{config.AD_CONTENT_INTENSITY_PERCENT}') in config. Defaulting to moderate intensity (20%).")
            intensity_percent = 20

        if not 0 <= intensity_percent <= 100:
            print(f"[WARN] AD_CONTENT_INTENSITY_PERCENT ({intensity_percent}) out of range (0-100). Clamping to nearest bound.")
            intensity_percent = max(0, min(100, intensity_percent))

        # Define instruction levels based on percentage
        if intensity_percent == 0:
            instruction = "Focus entirely on the news insight and value for the user. Mention Airmart only if absolutely essential and natural, keeping it extremely minimal."
        elif 1 <= intensity_percent <= 20:
            instruction = "Prioritize the news insight and general advice. Keep Airmart mentions very subtle and brief (max 1-2 times) only as a relevant tool."
        elif 21 <= intensity_percent <= 50:
            instruction = "Balance the news insight/advice with Airmart's relevance. Integrate Airmart naturally as a helpful solution, mentioning specific relevant features subtly."
        elif 51 <= intensity_percent <= 80:
            instruction = "Clearly connect the news insight to Airmart's benefits. Highlight relevant features more explicitly and explain how Airmart helps address the topic."
        else: # 81-100%
            instruction = "Make Airmart a central part of the solution/advice presented. Strongly emphasize how Airmart features address the news insight and promote its value in this context."

        print(f"[DEBUG] Generated Ad Intensity Instruction (for {intensity_percent}%): {instruction}")
        return instruction

    def _run_generation_step(self,
                             platform_name: str,
                             prompt_file: str,
                             language: str, # Language is now platform-specific
                             news_summary: str,
                             regenerate_component: str = 'all',
                             approved_text: Optional[str] = None,
                             approved_image_prompt: Optional[str] = None,
                             text_feedback: Optional[str] = None,
                             image_prompt_feedback: Optional[str] = None
                             ) -> Optional[Dict[str, Any]]:
        """Generates content for one platform using the AI service."""
        print(f"[WORKFLOW] --- Step: Content Generation ({platform_name}) ---")
        # Prepare inputs for AI service
        if not prompt_file or not os.path.exists(prompt_file):
            print(f"[ERROR]   Prompt file not found or not specified for {platform_name}: {prompt_file}")
            return None

        # Load base prompt messages
        print(f"[INFO]   Loading base prompt from: {prompt_file}")
        base_prompt_messages = load_prompt_from_file(prompt_file)
        if not base_prompt_messages:
            print(f"[ERROR]   Failed to load prompt messages from {prompt_file}")
            return None

        # Load Airmart context
        # print(f"[INFO]   Loading Airmart brand context...") # Debug
        airmart_context = load_airmart_context()
        if "Error:" in airmart_context:
            print(f"[WARN]   {airmart_context}. Using default/empty context.")
            airmart_context = ""

        # Generate ad intensity instruction
        ad_intensity_instruction = self._generate_ad_intensity_instruction()

        # Inject Airmart context and Ad Intensity Instruction into the prompt messages
        # Assumes placeholders {airmart_brand_context} and {ad_intensity_instruction} exist in the loaded prompt content
        injected_prompt_messages = []
        try:
            found_context_placeholder = False
            found_intensity_placeholder = False
            for msg in base_prompt_messages:
                new_msg = msg.copy()
                if isinstance(new_msg.get('content'), str):
                    if '{airmart_brand_context}' in new_msg['content']:
                        new_msg['content'] = new_msg['content'].replace('{airmart_brand_context}', airmart_context)
                        print("[DEBUG]   Injected Airmart brand context.")
                        found_context_placeholder = True
                    if '{ad_intensity_instruction}' in new_msg['content']:
                        new_msg['content'] = new_msg['content'].replace('{ad_intensity_instruction}', ad_intensity_instruction)
                        print("[DEBUG]   Injected Ad intensity instruction.")
                        found_intensity_placeholder = True
                injected_prompt_messages.append(new_msg)
            if not found_context_placeholder: print("[WARN]   Placeholder '{airmart_brand_context}' not found in prompt messages. Context not injected.")
            if not found_intensity_placeholder: print("[WARN]   Placeholder '{ad_intensity_instruction}' not found in prompt messages. Ad intensity not injected.")
        except Exception as e:
            print(f"[ERROR]   Failed to inject context/intensity into prompt: {e}")
            return None

        # Call AI service to generate content (this method now handles injection)
        # AI Service handles its own internal logging for the API call itself
        # print(f"[DEBUG] Calling generate_content with lang={language}, regen={regenerate_component}, news_len={len(news_summary or '')}") # Debug
        generated_content, error = self.ai_service.generate_content(
            platform_prompt_messages=injected_prompt_messages, # Use the messages with context injected
            target_language=language,
            news_summary=news_summary,
            regenerate_component=regenerate_component,
            approved_text=approved_text,
            approved_image_prompt=approved_image_prompt,
            text_feedback=text_feedback,
            image_prompt_feedback=image_prompt_feedback
        )

        if error:
            print(f"[ERROR]   Content generation failed for {platform_name}: {error}")
            return None

        return generated_content

    def _run_review_step(self, platform_content: Dict[str, Any], platform_name: str, language: str) -> Dict[str, Any]:
        """Runs AI and potentially Human review on a single generated post."""
        print(f"\n[WORKFLOW] --- Step: Reviewing {platform_name} Post ({language}) ---")
        step_result = {'status': 'rejected', 'feedback': {'error': 'Review step failed unexpectedly.'}}
        if not platform_content:
            step_result['feedback']['error'] = 'No content provided for review.'
            print(f"[ERROR]  {step_result['feedback']['error']}")
            return step_result

        try:
            print(f"[INFO]   --- AI Reviewing {platform_name} Components ---")
            # Initialize assuming AI reviews are skipped
            component_reviews = {
                'text': {'approved': True, 'feedback': 'AI review skipped by config.'},
                'image_prompt': {'approved': True, 'feedback': 'AI review skipped by config.'}
            }
            ai_approved_all_components = True # Start assuming all approved (or skipped)

            post_text_to_review = platform_content.get('post_text', '')
            image_prompt_to_review = platform_content.get('image_prompt', '')

            # --- AI Review Post Text (Conditional) ---
            if config.AI_REVIEW_ENABLED_POST_TEXT:
                print(f"[INFO]     Running AI Review for 'post_text'...")
                # AI Service handles internal logging for review calls
                text_review = self.ai_service.review_content(post_text_to_review, 'post_text', platform=platform_name, language=language)
                component_reviews['text'] = text_review # Update with actual review
                if not text_review.get('approved', False):
                    ai_approved_all_components = False
                print(f"[INFO]       Text AI Approved: {text_review.get('approved', False)}")
            else:
                print(f"[INFO]     Skipping AI Review for 'post_text' (disabled in config).")
                # Keep default component_reviews['text'] and ai_approved_all_components remains True for this part

            # --- AI Review Image Prompt (Conditional) ---
            if config.AI_REVIEW_ENABLED_IMAGE_PROMPT:
                print(f"[INFO]     Running AI Review for 'image_prompt'...")
                 # AI Service handles internal logging for review calls
                prompt_review = self.ai_service.review_content(image_prompt_to_review, 'image_prompt', platform=platform_name, language=language)
                component_reviews['image_prompt'] = prompt_review # Update with actual review
                if not prompt_review.get('approved', False):
                     ai_approved_all_components = False
                print(f"[INFO]       Image Prompt AI Approved: {prompt_review.get('approved', False)}")
            else:
                print(f"[INFO]     Skipping AI Review for 'image_prompt' (disabled in config).")
                # Keep default component_reviews['image_prompt'] and ai_approved_all_components remains True for this part

            step_result['feedback'] = component_reviews # Store final component reviews (skipped or actual)
            print(f"[INFO]   --- AI Review(s) Complete (Overall AI Approved Status: {ai_approved_all_components}) ---")

            # --- Human Review Trigger ---
            if not ai_approved_all_components or self.human_review_required_post:
                print(f"[INFO]   Triggering human review for post (AI Approved All: {ai_approved_all_components}, Human Review Required: {self.human_review_required_post})")
                # Reviewer handles its own logging
                human_review = self.reviewer.request_review(
                    content_to_review=platform_content,
                    content_type='full_post',
                    ai_feedback=component_reviews,
                    platform=platform_name,
                    language=language # Pass platform language
                )
                step_result['status'] = 'approved' if human_review.get('approved', False) else 'rejected'
                # Ensure feedback from human review is structured correctly
                human_feedback = human_review.get('feedback', {})
                step_result['feedback'] = {
                     'text': human_feedback.get('text', {'approved': step_result['status'] == 'approved', 'feedback': 'N/A'}),
                     'image_prompt': human_feedback.get('image_prompt', {'approved': step_result['status'] == 'approved', 'feedback': 'N/A'})
                 }

                # Human review outcome logged by reviewer
                # if step_result['status'] == 'approved':
                #      print(f"[INFO]   Human approved {platform_name} post.")
                # else:
                #      print(f"[INFO]   Human rejected {platform_name} post.")
            elif ai_approved_all_components:
                print(f"[INFO]   Skipping Human Review ({platform_name} Post - AI Approved & Not Required). Status: Approved.")
                step_result['status'] = 'approved'
                # Feedback structure is already set from AI review
                step_result['feedback'] = component_reviews

            return step_result

        except Exception as e:
             print(f"[ERROR]  Critical error during review step for {platform_name}: {e}")
             traceback.print_exc()
             step_result['status'] = 'rejected'
             step_result['feedback'] = {'error': f'Critical error in review step: {e}'}
             return step_result

    # --------------------------------------------------------------------------
    # Public Method to Run the Workflow
    # --------------------------------------------------------------------------

    def run(self): # Removed language and country parameters
        """
        Orchestrates the full multi-step content generation workflow for all platforms,
        using language settings from config.py.
        """
        print(f"\n[WORKFLOW] <<<<< Starting Content Workflow Run >>>>>")
        start_time = time.time()
        links_from_approved_news: List[str] = [] # Only store links if news is approved
        final_approved_content: Dict[str, Optional[Dict[str, Any]]] = {'Instagram': None, 'Rednote': None} # Track final results
        any_post_saved = False # Track if we actually save anything

        try:
            # Load history BEFORE fetching news
            used_links_history = self.storage.load_used_article_links()

            # --- News Step --- (Logs internally)
            news_result = self._run_news_step(used_links=used_links_history)

            if news_result['status'] == 'rejected':
                print(f"[WORKFLOW] --- Workflow halted: News step failed or was rejected. ---")
                # Feedback logged internally by _run_news_step or AI/Human review
                print("[WORKFLOW] <<<<< Workflow Run Ended (Failed at News Stage) >>>>>")
                return
            elif news_result['status'] == 'no_news':
                print("[WORKFLOW] --- Workflow halted: No new news articles found. --- ")
                print("[WORKFLOW] <<<<< Workflow Run Ended (No New News) >>>>>")
                return

            # News approved, store the summary and links
            approved_news = news_result['news_summary']
            # IMPORTANT: `fetched_articles` now ONLY contains the LINKS of articles USED in the approved summary
            links_from_approved_news = news_result.get('fetched_articles', [])
            print(f"[INFO]   News approved. Proceeding to content generation for platforms.")
            print(f"[INFO]   {len(links_from_approved_news)} article link(s) from approved news will be marked as used if any posts are saved.")

            # Dictionary mapping platform names to their config settings
            platform_configs = {
                 "Instagram": {"prompt_file": config.INSTAGRAM_PROMPT_FILE, "language": config.INSTAGRAM_LANGUAGE},
                 "Rednote": {"prompt_file": config.REDNOTE_PROMPT_FILE, "language": config.REDNOTE_LANGUAGE}
             }

            platform_states: Dict[str, Dict[str, Any]] = {
                p_name: {"content": None, "review_outcome": None, "attempts": 0}
                for p_name in platform_configs.keys()
            }

            # --- Platform Processing Loop ---
            for platform, p_config in platform_configs.items():
                prompt_file = p_config["prompt_file"]
                platform_language = p_config["language"] # Get language from config
                platform_state = platform_states[platform]

                print(f"\n[WORKFLOW] ===== Processing Platform: {platform} (Language: {platform_language}) =====")

                for attempt in range(self.max_regen_attempts + 1):
                    print(f"\n== {platform} - Attempt {attempt + 1}/{self.max_regen_attempts + 1} ==")
                    platform_state["attempts"] = attempt + 1

                    regenerate_component = 'all'
                    text_feedback_for_regen = None
                    image_prompt_feedback_for_regen = None
                    approved_text_for_regen = None
                    approved_image_prompt_for_regen = None # Use separate vars for clarity


                    previous_review = platform_state.get("review_outcome")
                    previous_content = platform_state.get("content")

                    if attempt > 0 and previous_review and previous_review.get('status') == 'rejected':
                        print("Analyzing feedback for targeted regeneration...")
                        structured_fb = previous_review.get('feedback', {})
                        # Default to False if keys are missing
                        text_approved = structured_fb.get('text', {}).get('approved', False)
                        prompt_approved = structured_fb.get('image_prompt', {}).get('approved', False)
                        text_fb = structured_fb.get('text', {}).get('feedback')
                        prompt_fb = structured_fb.get('image_prompt', {}).get('feedback')


                        approved_text_for_regen = previous_content.get('post_text') if previous_content and text_approved else None
                        approved_image_prompt_for_regen = previous_content.get('image_prompt') if previous_content and prompt_approved else None


                        if text_approved and not prompt_approved:
                            regenerate_component = 'image_prompt'
                            image_prompt_feedback_for_regen = prompt_fb
                            print(f"Target: IMAGE PROMPT. Feedback: {image_prompt_feedback_for_regen}")
                        elif not text_approved and prompt_approved:
                            regenerate_component = 'text'
                            text_feedback_for_regen = text_fb
                            print(f"Target: TEXT. Feedback: {text_feedback_for_regen}")
                        else: # Both rejected or feedback structure issue
                            regenerate_component = 'all'
                            text_feedback_for_regen = text_fb if not text_approved else None
                            image_prompt_feedback_for_regen = prompt_fb if not prompt_approved else None
                            print(f"Target: ALL. Text FB: {text_feedback_for_regen}, Img FB: {image_prompt_feedback_for_regen}")
                            # Reset approved components if regenerating all based on rejection
                            approved_text_for_regen = None
                            approved_image_prompt_for_regen = None
                    else:
                         print("Generating initial content or retrying full generation.")
                         regenerate_component = 'all'
                         # Ensure these are None for initial generation
                         approved_text_for_regen = None
                         approved_image_prompt_for_regen = None


                    current_content = self._run_generation_step(
                        platform_name=platform,
                        prompt_file=prompt_file,
                        language=platform_language, # Pass platform language
                        news_summary=approved_news,
                        regenerate_component=regenerate_component,
                        approved_text=approved_text_for_regen,
                        approved_image_prompt=approved_image_prompt_for_regen,
                        text_feedback=text_feedback_for_regen,
                        image_prompt_feedback=image_prompt_feedback_for_regen
                    )
                    platform_state["content"] = current_content

                    if not current_content:
                        print(f"Generation failed for {platform} on attempt {attempt + 1}.")
                        platform_state["review_outcome"] = {'status': 'rejected', 'feedback': {'error': 'Generation failed'}}
                        if attempt >= self.max_regen_attempts:
                            print(f"Max generation attempts reached for {platform}. Stopping.")
                            break
                        else:
                            print("Retrying generation...")
                            time.sleep(2) # Small delay before retry
                            continue

                    review_outcome = self._run_review_step(
                        platform_content=current_content,
                        platform_name=platform,
                        language=platform_language # Pass platform language
                        )
                    platform_state["review_outcome"] = review_outcome

                    if review_outcome.get('status') == 'approved':
                        print(f"{platform} content APPROVED on attempt {attempt + 1}.")
                        final_approved_content[platform] = current_content # Store approved content
                        break # Exit attempt loop for this platform
                    else:
                        print(f"{platform} content REJECTED on attempt {attempt + 1}.")
                        if attempt >= self.max_regen_attempts:
                            print(f"Max review/regeneration attempts reached for {platform}. Content remains rejected.")
                            final_approved_content[platform] = None # Ensure it's marked as not approved
                            break # Exit attempt loop

                # --- Save approved content for this platform ---
                if final_approved_content[platform]:
                     # Extract the approved content and prompt
                     approved_content_dict = final_approved_content[platform]
                     image_prompt = approved_content_dict.get('image_prompt', None)
                     image_url = None # Initialize image_url

                     # Generate image only if there is a prompt
                     if image_prompt:
                          # Use standard INFO prefix
                          print(f"[INFO]   Attempting to generate image for {platform} ({platform_language})...")
                          # Determine appropriate size based on platform
                          # Default DALL-E 3 sizes: 1024x1024, 1792x1024, 1024x1792
                          img_size = "1024x1024" # Default square
                          if platform == "Instagram":
                              img_size = "1024x1792" # Vertical 4:5 aspect ratio for Instagram is approximated by this
                          elif platform == "Rednote":
                              img_size = "1024x1792" # Vertical often preferred (3:4 or 9:16, 1024x1792 is closest)

                          # AI Service handles its own logging for the generation call
                          image_url, img_error = self.ai_service.generate_image(prompt=image_prompt, size=img_size)
                          if img_error:
                               # Use standard WARN prefix
                               print(f"[WARN]   Image generation failed for {platform}: {img_error}. Saving post without image URL.")
                          # else: image_url is set, AI Service logs success
                     else:
                         # Use standard INFO prefix
                         print(f"[INFO]   Skipping image generation for {platform} ({platform_language}) as no image prompt was found.")

                     try:
                         # Pass the generated image_url (which might be None) to save_content
                         # Storage service handles its own logging
                         self.storage.save_content(platform, platform_language, approved_content_dict, image_url)
                         any_post_saved = True # Mark that at least one post was saved
                     except Exception as e:
                          # Use standard ERROR prefix
                          print(f"[ERROR]  Error saving content or processing image for {platform} ({platform_language}): {e}")
                          final_approved_content[platform] = None # Mark as failed if save error occurs


            # --- Final Reporting & Saving Used Links ---
            print("\n[WORKFLOW] --- Step: Final Report & Saving Used Links ---")
            platforms_succeeded = [p for p, c in final_approved_content.items() if c]
            platforms_failed = [p for p, c in final_approved_content.items() if not c]
            # Re-evaluate any_success based on whether content was actually kept (not None due to saving error)
            any_success = bool(platforms_succeeded)

            if links_from_approved_news and any_post_saved:
                 # Storage handles its own logging
                 self.storage.append_used_article_links(links_from_approved_news)
            elif not any_post_saved:
                 print("[INFO]   No posts were approved/saved. Skipping saving of used article links for this run.")
            else: # Links exist from approved news, but no posts were saved (all failed generation/review/saving)
                 print("[INFO]   News was approved, but no posts were successfully generated/saved. Skipping saving of used article links.")


            if any_success:
                success_str = ', '.join(platforms_succeeded)
                fail_str = ', '.join(platforms_failed) if platforms_failed else 'None'
                overall_status = 'Full Success' if len(platforms_succeeded) == len(final_approved_content) else 'Partial Success'
                # Use WORKFLOW prefix for final status
                print(f"\n[WORKFLOW] ===== Workflow Run Completed ({overall_status}) =====")
                print(f"[WORKFLOW]   Successfully processed platforms: {success_str}")
                print(f"[WORKFLOW]   Failed/Skipped platforms: {fail_str}")
            else:
                # Use WORKFLOW prefix for final status
                print("\n[WORKFLOW] ===== Workflow Run Completed (No content approved/saved) =====")


        except Exception as e:
            print(f"\n[ERROR] !!! CRITICAL WORKFLOW ERROR: An unexpected error occurred during the run: {e} !!!")
            traceback.print_exc()
            # Attempt to save any links collected *before* the critical error, if any posts succeeded before crash
            if links_from_approved_news and any_post_saved:
                 print("\n[INFO]   Attempting to save collected article links before exiting due to error...")
                 try:
                     self.storage.append_used_article_links(links_from_approved_news)
                 except Exception as save_e:
                     print(f"[ERROR]    Failed to save links during error handling: {save_e}")
            print("[WORKFLOW] <<<<< Workflow Run Ended Prematurely due to Error >>>>>")
        finally: # Ensure finally block is present and correctly indented
            end_time = time.time()
            print(f"[WORKFLOW] <<<<< Workflow Run Finished in {end_time - start_time:.2f} seconds >>>>>") 