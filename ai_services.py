import openai
import json
import traceback
from typing import Tuple, List, Dict, Any, Optional
# Import the summarization utility function
from summarizer_agent import summarize_with_llm

class AIService:
    """Handles interactions with the OpenAI API for content generation and review."""

    def __init__(self, api_key: str, generation_model: str, review_model: str, base_url: Optional[str] = None):
        try:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url # Use provided base_url if available
            )
            self.generation_model = generation_model
            self.review_model = review_model
            print(f"[INFO] AIService initialized. Generation Model: {generation_model}, Review Model: {review_model}, Base URL: {base_url or 'Default OpenAI'}")
        except Exception as e:
            print(f"[ERROR] Fatal Error initializing AIService: {e}")
            traceback.print_exc() # Keep traceback for fatal errors
            raise # Reraise to prevent execution with invalid client

    def generate_content(self,
        platform_prompt_messages: list,
        target_language: str = 'en',
        news_summary: str = None,
        regenerate_component: str = 'all', # 'all', 'text', or 'image_prompt'
        approved_text: str = None,
        approved_image_prompt: str = None,
        text_feedback: str = None,
        image_prompt_feedback: str = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Generates social post content using the configured model.

        Handles optional news summaries and regeneration logic based on feedback.
        Ensures the output is a JSON object with 'post_text', 'image_prompt', and 'hashtags'.

        Returns: Tuple[Generated content dict or None, Error message or None]
        """
        if not platform_prompt_messages:
            print("[ERROR] generate_content called with empty prompt messages.")
            return None, "Error: Prompt messages were empty."

        messages = [msg.copy() for msg in platform_prompt_messages]
        regeneration_instructions = ""

        # --- Construct Regeneration Instructions ---
        # Based on feedback, construct specific instructions for the LLM
        # to regenerate only parts of the content or the entire content.
        if regenerate_component == 'text':
            regeneration_instructions = f"**IMPORTANT:** Please regenerate ONLY the 'post_text' and potentially related 'hashtags'. The previous text was rejected with the following feedback: '{text_feedback}'. "
            if approved_image_prompt:
                regeneration_instructions += f"Keep the following approved image prompt in mind for context:\n```\n{approved_image_prompt}\n```\n"
            regeneration_instructions += "Output the full JSON including the regenerated 'post_text', potentially updated 'hashtags', and the **original** 'image_prompt'."
        elif regenerate_component == 'image_prompt':
            regeneration_instructions = f"**IMPORTANT:** Please regenerate ONLY the 'image_prompt'. The previous prompt was rejected with the following feedback: '{image_prompt_feedback}'. "
            if approved_text:
                regeneration_instructions += f"Keep the following approved post text in mind for context:\n```\n{approved_text}\n```\n"
            regeneration_instructions += "Output the full JSON including the regenerated 'image_prompt', the **original** 'post_text', and the **original** 'hashtags'."
        elif regenerate_component == 'all' and (text_feedback or image_prompt_feedback):
            # Combine feedback if regenerating all based on previous rejection
            combined_feedback = []
            if text_feedback: combined_feedback.append(f"Text Feedback: '{text_feedback}'")
            if image_prompt_feedback: combined_feedback.append(f"Image Prompt Feedback: '{image_prompt_feedback}'")
            feedback_str = ", ".join(combined_feedback) if combined_feedback else "N/A"
            regeneration_instructions = f"**IMPORTANT:** Please regenerate the content. The previous attempt was rejected. Feedback: {feedback_str}. Please address these points carefully. Output the full JSON (post_text, image_prompt, hashtags)."

        # --- Inject Instructions, Language, and News ---
        try:
            # Locate the user message to inject dynamic content
            user_message_index = -1
            for i, msg in enumerate(messages):
                if msg.get("role") == "user": user_message_index = i; break
            if user_message_index == -1: raise ValueError("Could not find user message in prompt.")

            # Inject Target Language
            lang_placeholder = "{output_language}"
            if lang_placeholder in messages[user_message_index]["content"]:
                 messages[user_message_index]["content"] = messages[user_message_index]["content"].replace(lang_placeholder, target_language)
                 print(f"[DEBUG] Replaced language placeholder with '{target_language}'.")
            else:
                 # Append if placeholder is missing
                 messages[user_message_index]["content"] += f"\n\n**Output Language:** {target_language}"
                 print(f"[DEBUG] Appended language instruction: '{target_language}'.")

            # Inject News Summary (if provided and placeholder exists)
            if news_summary:
                news_placeholder_text = "{News summary}"
                # Limit logged length for brevity
                news_injection_text = f"Use the following news insight:\n```\n{news_summary[:200]}...\n```"
                if news_placeholder_text in messages[user_message_index]["content"]:
                     messages[user_message_index]["content"] = messages[user_message_index]["content"].replace(news_placeholder_text, news_injection_text)
                     print(f"[DEBUG] Replaced news placeholder with summary (preview: {news_summary[:50]}...).")
                else:
                    # Design decision: Require placeholder for news injection
                    print(f"[WARN] News summary provided, but placeholder '{news_placeholder_text}' not found in user prompt. News not injected.")

            # Inject Regeneration Instructions (if applicable)
            if regeneration_instructions:
                messages[user_message_index]["content"] += f"\n\n{regeneration_instructions}"
                print(f"[INFO] Injecting regeneration instructions (Component: {regenerate_component}). Preview: {regeneration_instructions[:100]}...")

        except Exception as e:
            print(f"[ERROR] Error preparing prompt for generation: {e}")
            traceback.print_exc()
            return None, f"Error preparing prompt: {e}"

        # --- API Call ---
        try:
            print(f"[INFO] ---> Calling OpenAI ChatCompletion ({self.generation_model}) for content generation...")
            # print(f"[DEBUG] Messages sent: {json.dumps(messages, indent=2)}") # Keep optional debug log commented
            response = self.client.chat.completions.create(
                model=self.generation_model,
                messages=messages,
                # Tool calls are currently disabled; functionality can be added here if needed
                # tools=news_fetcher_tools,
                # tool_choice="auto",
                temperature=0.8, # Higher temperature for creative generation
                response_format={"type": "json_object"} # Ensure JSON output
            )
            print("[INFO] <--- OpenAI ChatCompletion call successful.")
            response_message = response.choices[0].message

            # Direct content usage as tool calls are disabled
            final_content_string = response_message.content

            # --- Parse and Merge Final Content ---
            try:
                print("[INFO] Parsing final content JSON...")
                parsed_content = json.loads(final_content_string)

                # Validate basic structure and fill defaults if keys are missing
                if not isinstance(parsed_content, dict):
                     print("[ERROR] LLM response was not a JSON object.")
                     raise ValueError("LLM response is not a JSON object.")
                if not all(key in parsed_content for key in ["post_text", "image_prompt", "hashtags"]):
                    print(f"[WARN] Parsed JSON missing expected keys. Got: {list(parsed_content.keys())}. Filling with defaults.")
                    parsed_content.setdefault('post_text', None)
                    parsed_content.setdefault('image_prompt', None)
                    parsed_content.setdefault('hashtags', [])

                # Merging logic for partial regeneration: Use approved parts from previous step
                final_merged_content = parsed_content.copy()
                if regenerate_component == 'text' and approved_image_prompt:
                    print("[INFO] Merging: Using provided approved image prompt.")
                    final_merged_content['image_prompt'] = approved_image_prompt
                elif regenerate_component == 'image_prompt' and approved_text:
                    print("[INFO] Merging: Using provided approved post text.")
                    final_merged_content['post_text'] = approved_text
                    # If LLM didn't provide new hashtags during image prompt regen, they might be lost.
                    # Requires explicitly passing original hashtags if needed.
                    if 'hashtags' not in parsed_content or not parsed_content['hashtags']:
                         print("[WARN] Merging: LLM did not provide hashtags during image prompt regeneration.")


                print(f"[INFO] Content generation successful. Final keys: {list(final_merged_content.keys())}")
                return final_merged_content, None

            except json.JSONDecodeError:
                print(f"[ERROR] Failed to parse JSON response from LLM: {final_content_string}")
                return None, f"Failed to parse JSON response: {final_content_string}"
            except Exception as e:
                print(f"[ERROR] Error processing final content after JSON parsing: {e}")
                traceback.print_exc()
                return None, f"Error processing final content: {e}"

        # --- API Exception Handling ---
        except openai.APIError as e:
            print(f"[ERROR] OpenAI API Error (Generation): {e}")
            return None, f"OpenAI API Error: {e}"
        except openai.APIConnectionError as e:
            print(f"[ERROR] OpenAI Connection Error (Generation): {e}")
            return None, f"OpenAI Connection Error: {e}"
        except openai.RateLimitError as e:
            print(f"[ERROR] OpenAI Rate Limit Error (Generation): {e}")
            return None, f"OpenAI Rate Limit Error: {e}"
        except openai.AuthenticationError as e:
            print(f"[ERROR] OpenAI Authentication Error (Generation): {e}")
            return None, f"OpenAI Authentication Error: {e}"
        except openai.BadRequestError as e:
            print(f"[ERROR] OpenAI Bad Request Error (Generation): {e}")
            return None, f"OpenAI Bad Request Error: {e}"
        except Exception as e:
            print(f"[ERROR] Unexpected Error during generation API call: {e}")
            traceback.print_exc()
            return None, f"Unexpected Error during generation: {e}"

    def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard", n: int = 1) -> Tuple[Optional[str], Optional[str]]:
        """
        Generates an image using DALL-E 3 based on the provided prompt.

        Args:
            prompt: The text prompt for image generation.
            size: The desired size ("1024x1024", "1024x1792", "1792x1024").
            quality: The quality ("standard" or "hd").
            n: Number of images (currently only 1 is supported).

        Returns:
            Tuple[Image URL or None, Error message or None].
        """
        if not prompt:
            print("[ERROR] generate_image called with empty prompt.")
            return None, "Error: Image generation prompt was empty."

        print(f"[INFO] ---> Calling OpenAI Image Generation (DALL-E 3)...")
        print(f"[INFO]   Prompt (Preview): {prompt[:100]}...")
        print(f"[INFO]   Size: {size}, Quality: {quality}, N: {n}")

        try:
            response = self.client.images.generate(
                model="dall-e-3", # Using DALL-E 3 specifically
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
                response_format="url" # Request URL directly for simplicity
            )
            print("[INFO] <--- OpenAI Image Generation call successful.")

            # Extract URL assuming n=1
            if response.data and len(response.data) > 0:
                image_url = response.data[0].url
                if image_url:
                    print(f"[INFO] Image generated successfully. URL: {image_url}")
                    return image_url, None
                else:
                    print("[ERROR] API response did not contain a valid image URL.")
                    return None, "Error: API response did not contain a valid image URL."
            else:
                print("[ERROR] API response did not contain image data.")
                return None, "Error: API response did not contain image data."

        except openai.APIError as e:
            print(f"[ERROR] OpenAI API Error (Image Gen): {e}")
            return None, f"OpenAI API Error (Image Gen): {e}"
        except openai.APIConnectionError as e:
            print(f"[ERROR] OpenAI Connection Error (Image Gen): {e}")
            return None, f"OpenAI Connection Error (Image Gen): {e}"
        except openai.RateLimitError as e:
            print(f"[ERROR] OpenAI Rate Limit Error (Image Gen): {e}")
            return None, f"OpenAI Rate Limit Error (Image Gen): {e}"
        except openai.AuthenticationError as e:
            print(f"[ERROR] OpenAI Authentication Error (Image Gen): {e}")
            return None, f"OpenAI Authentication Error (Image Gen): {e}"
        except openai.BadRequestError as e:
            # Specific handling for DALL-E errors (e.g., content policy violations)
            print(f"[ERROR] OpenAI Bad Request Error (Image Gen): {e}")
            error_details = e.body.get('error', {}) if e.body else {}
            error_message = error_details.get('message', str(e))
            print(f"[ERROR]   Details: {error_message}")
            return None, f"OpenAI Bad Request Error (Image Gen): {error_message}"
        except Exception as e:
            print(f"[ERROR] Unexpected Error during image generation: {e}")
            traceback.print_exc()
            return None, f"Unexpected Error during image generation: {e}"

    def review_content(self, content_to_review: str, content_type: str, platform: Optional[str] = None, language: str = 'en') -> Dict[str, Any]:
        """
        Uses the configured review model to assess content against predefined criteria.

        Dynamically loads criteria based on content_type and platform.
        Requires the LLM to respond in a specific JSON format: {"approved": bool, "feedback": str}.
        """
        print(f"[INFO] ---> AI Reviewing Content...")
        print(f"[INFO]   Type: {content_type}, Platform: {platform or 'N/A'}, Language: {language}, Model: {self.review_model}")
        if not content_to_review:
            print("[WARN] Content to review was empty.")
            return {'approved': False, 'feedback': 'AI feedback: Content to review was empty.'}
        print(f"[INFO]   Content (Preview): {content_to_review[:200]}...")

        # --- Define Review Criteria Dynamically ---
        criteria = ""
        if content_type == 'news_summary':
            criteria = """
            - Relevance: Is this news relevant to e-commerce businesses?
            - Timeliness: Does the news seem recent?
            - Clarity: Is the summary clear and understandable?
            - Actionability: Potential insights/discussion points?
            """
        elif content_type == 'post_text':
            platform_specifics = ""
            if platform == 'Instagram':
                platform_specifics = f"""- Platform Fit (Instagram):
                    - Engaging hook & style?
                    - Body text concise (~100-150 words)?
                    - **Readability:** Uses short paragraphs (separated by '\n\n')?
                    - **Visual Appeal:** Includes appropriate emojis (approx. 2-4 in body + hook)?
                    - Clear CTA?
                    - Appropriate for language '{language}'?
                """
            elif platform == 'Rednote':
                # Specific criteria for Rednote/Xiaohongshu
                platform_specifics = f"""- Platform Fit (Rednote):
                    - Authenticity & Value: Is the tone authentic, relatable, and focused on providing value ("干货") or solving a problem?
                    - Title: Is the title catchy, concise (<20 chars), use "爆款关键词" effectively, and reflect the core value?
                    - Content Structure: Is the content well-structured (e.g., using paragraphs, possibly lists/emojis for readability) for mobile viewing?
                    - Natural Integration: Is Airmart integrated naturally as a helpful solution linked to the News Insight, avoiding hard sells?
                    - Engagement Encouragement: Does it encourage interaction (comments, questions) and specifically SAVES?
                    - Platform Tone: Does it have the appropriate Xiaohongshu "网感" (net-sense) and personal sharing style?
                    - Storytelling: Does it effectively use storytelling where appropriate?
                    - Language: Is the style appropriate for Simplified Chinese (zh-CN)?
                """
            criteria = f"""
            - Brand Voice (Airmart): Does the tone feel empowering, supportive, practical, community-focused, accessible, and innovative?
            - Relevance to News: Does the post accurately interpret and leverage the provided News Insight to offer value?
            - Relevance to Airmart: Does the post naturally and subtly connect the value proposition to Airmart's features/benefits? (Not just mention the name).
            - Target Audience Appeal: Does it resonate with and provide value to small business owners/creators on the platform?
            - Clarity & Grammar: Is the text clear, well-written, and free of grammatical errors in the specified language '{language}'?
            {platform_specifics}
            - Call to Action: Is the CTA clear, appropriate for the platform, and aligned with the content's goal (e.g., engagement, exploration)?
            """
        elif content_type == 'image_prompt':
            platform_specifics = ""
            if platform == 'Instagram':
                platform_specifics = """- Platform Fit (Instagram):
                    - Visual style aligns with brand (professional yet relatable)?
                    - Specifies 4:5 aspect ratio & HD quality?
                """
            elif platform == 'Rednote':
                platform_specifics = """- Platform Fit (Rednote):
                    - Visual Style: Does it describe an eye-catching, authentic, aesthetically pleasing visual suitable for Xiaohongshu? Does it align with the post's content (e.g., real usage, results, relatable scenario)?
                    - Text Overlay: Does it mention necessary/effective text overlays for the cover image, if appropriate?
                    - Technical Specs: Does it explicitly specify a vertical aspect ratio (3:4 or 9:16) and HD quality?
                """
            criteria = f"""
            - Clarity & Detail: Is the prompt specific and detailed enough for an AI image generation model to create a relevant image?
            - Relevance to Text: Does the described image align logically and thematically with the corresponding post_text and the core message derived from the News Insight?
            - Brand Alignment: Does the visual concept fit Airmart's brand identity (supporting small businesses/creators)?
            {platform_specifics}
            - Safety/Policy: Is the requested image safe, compliant with platform policies, and appropriate?
            """
        else:
             print(f"[ERROR] Unknown content type '{content_type}' provided for review.")
             return {'approved': False, 'feedback': f'AI feedback: Unknown content type "{content_type}" for review.'}

        # --- Construct the LLM Prompt for Review ---
        # Provide clear instructions and examples for the required JSON output format
        example_approved_dict = {"approved": True, "feedback": "Meets criteria."}
        example_rejected_dict = {"approved": False, "feedback": "Tone too generic."}
        example_approved_str = json.dumps(example_approved_dict)
        example_rejected_str = json.dumps(example_rejected_dict)

        prompt_base = f"""
        You are an AI quality assurance agent reviewing content for Airmart.
        Review the following '{content_type}' for {platform or 'internal use'} in language '{language}'.

        Content to Review:
        ```
        {content_to_review}
        ```

        Review Criteria:
        {criteria}

        Respond ONLY with a valid JSON object containing two keys: "approved" (boolean) and "feedback" (string explaining decision).
        The format MUST be exactly: {{"approved": boolean, "feedback": "string"}}
        """

        prompt_examples = f"""
        Example Approved JSON object:
        {example_approved_str}

        Example Rejected JSON object:
        {example_rejected_str}
        """

        review_prompt = prompt_base + "\n" + prompt_examples

        # --- API Call for Review ---
        try:
            # print(f"[DEBUG] Review prompt: {review_prompt}") # Optional debug
            response = self.client.chat.completions.create(
                model=self.review_model,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.2, # Lower temperature for more deterministic review
                response_format={"type": "json_object"}, # Enforce JSON output
            )
            print("[INFO] <--- AI Review call successful.")
            review_result_str = response.choices[0].message.content
            try:
                review_result = json.loads(review_result_str)
                # Validate the structure of the returned JSON
                if 'approved' not in review_result or 'feedback' not in review_result:
                     print(f"[ERROR] Invalid review response format from LLM: {review_result_str}")
                     return {'approved': False, 'feedback': f'AI feedback: Invalid review response format: {review_result_str}'}

                print(f"[INFO] AI Review Outcome: {'Approved' if review_result['approved'] else 'Rejected'}")
                print(f"[INFO] AI Feedback: {review_result['feedback']}")
                return review_result
            except json.JSONDecodeError:
                 print(f"[ERROR] Failed to parse JSON review response: {review_result_str}")
                 return {'approved': False, 'feedback': f'AI feedback: Failed to parse JSON review response: {review_result_str}'}
        except Exception as e:
            print(f"[ERROR] Error during AI review API call: {e}")
            traceback.print_exc()
            return {'approved': False, 'feedback': f'AI Review Failed: {e}'}

    def summarize_article_text(self, text_to_summarize: str) -> str:
        """Summarizes the given article text using the summarizer utility function."""
        if not text_to_summarize:
            print("[WARN] No text provided to summarize_article_text.")
            return "[Error: No text provided for summarization.]"

        print(f"[INFO] ---> Calling LLM for Summarization ({self.review_model})...")
        # Delegate summarization to the dedicated function, passing the client and model
        # summarize_with_llm handles its own API call and logging
        summary = summarize_with_llm(
            client=self.client,
            text_to_summarize=text_to_summarize,
            model=self.review_model
        )
        # Log the result from this service's perspective
        if summary.startswith("[Error") or summary.startswith("[Unexpected"):
            print(f"[WARN] Summarization returned an error message: {summary}")
        else:
            print(f"[INFO] <--- Summarization successful (via summarize_with_llm).")
        return summary 