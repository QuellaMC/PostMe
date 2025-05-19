import json
from typing import Dict, Any

class ConsoleReviewer:
    """Handles the human review process via console interaction."""

    def request_review(
        self,
        content_to_review: Dict[str, Any] | str,
        content_type: str,
        ai_feedback: Dict[str, Any],
        platform: str | None = None,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Simulates human review via console input. Returns structured feedback.
        For 'full_post', reviews 'post_text' and 'image_prompt' separately.
        For 'news_summary', performs a single approval check.

        Args:
            content_to_review: The content dict (for post) or string (for news).
            content_type: 'full_post' or 'news_summary'.
            ai_feedback: Structured AI feedback for components (or single feedback for news).
            platform: Platform name (e.g., 'Instagram').
            language: Language code.

        Returns:
            A dictionary with 'approved' (bool) and 'feedback' (structured dict).
        """
        print(f"\n L__ [HUMAN ACTION REQUIRED] Review {content_type} ({platform or 'News Summary'}, {language}) __/")

        human_approved_overall = True
        # Default structure assumes approval, gets overridden on rejection
        structured_feedback = {
            'text': {'approved': True, 'feedback': 'Human approved or N/A.'},
            'image_prompt': {'approved': True, 'feedback': 'Human approved or N/A.'}
        }

        if content_type == 'full_post' and isinstance(content_to_review, dict):
            # --- Review Text ---
            print("\n  > Reviewing Post Text:")
            print("    " + "-"*30) # Separator
            print("    TEXT CONTENT:")
            post_text = content_to_review.get('post_text', '[NO TEXT FOUND]')
            indented_text = post_text.replace('\n', '\n    ')
            print(f"    ```\n    {indented_text}\n    ```")
            print("    " + "-"*30)
            print(f"    AI Feedback (Text): {ai_feedback.get('text', {}).get('feedback', 'N/A')}")
            while True:
                text_approval = input("  ? Approve Post Text? (y/n): ").lower().strip()
                if text_approval in ['y', 'n']:
                    break
                print("    [!] Please enter 'y' or 'n'.")
            if text_approval == 'n':
                human_approved_overall = False
                text_fb = input("  > Provide feedback for Post Text: ")
                structured_feedback['text'] = {'approved': False, 'feedback': text_fb}
            else:
                 structured_feedback['text'] = {'approved': True, 'feedback': 'Human approved.'}

            # --- Review Image Prompt ---
            print("\n  > Reviewing Image Prompt:")
            print("    " + "-"*30) # Separator
            print(f"    IMAGE PROMPT:")
            image_prompt = content_to_review.get('image_prompt', '[NO IMAGE PROMPT FOUND]')
            indented_prompt = image_prompt.replace('\n', '\n    ')
            print(f"    ```\n    {indented_prompt}\n    ```")
            print("    " + "-"*30)
            print(f"    AI Feedback (Image Prompt): {ai_feedback.get('image_prompt', {}).get('feedback', 'N/A')}")
            while True:
                prompt_approval = input("  ? Approve Image Prompt? (y/n): ").lower().strip()
                if prompt_approval in ['y', 'n']:
                     break
                print("    [!] Please enter 'y' or 'n'.")
            if prompt_approval == 'n':
                human_approved_overall = False
                prompt_fb = input("  > Provide feedback for Image Prompt: ")
                structured_feedback['image_prompt'] = {'approved': False, 'feedback': prompt_fb}
            else:
                structured_feedback['image_prompt'] = {'approved': True, 'feedback': 'Human approved.'}

        elif content_type == 'news_summary' and isinstance(content_to_review, str):
            print("\n  > Reviewing News Summary:")
            print("    " + "-"*30)
            print(f"    NEWS SUMMARY (Preview):")
            news_summary = content_to_review[:1000]
            indented_summary = news_summary.replace('\n', '\n    ')
            print(f"    ```\n    {indented_summary}...") # Indent preview
            print("    ```")
            print("    " + "-"*30)
            # News AI feedback is typically a single string under the top-level 'feedback' key
            print(f"    AI Feedback: {ai_feedback.get('feedback', 'N/A')}")
            while True:
                news_approval = input("  ? Approve News Summary? (y/n): ").lower().strip()
                if news_approval in ['y', 'n']:
                    break
                print("    [!] Please enter 'y' or 'n'.")
            if news_approval == 'n':
                human_approved_overall = False
                news_fb = input("  > Provide feedback for News Summary: ")
                # Store news feedback under 'text' for consistency
                structured_feedback['text'] = {'approved': False, 'feedback': news_fb}
                structured_feedback['image_prompt'] = {'approved': False, 'feedback': 'N/A - News has no image prompt'}
            else:
                 # Explicitly confirm approval state for news summary
                 structured_feedback['text'] = {'approved': True, 'feedback': 'Human approved.'}
                 structured_feedback['image_prompt'] = {'approved': True, 'feedback': 'N/A - News has no image prompt'}
        else:
            print(f"[WARN] Human review requested for unhandled content type '{content_type}' or incorrect data format. Skipping.")
            # Return a clear rejection status
            return {'approved': False, 'feedback': {'error': f"Unhandled content type/format for human review: {content_type}"}}

        print(f"\n[INFO] Human Review Outcome: {'Approved' if human_approved_overall else 'Rejected'}")
        return {'approved': human_approved_overall, 'feedback': structured_feedback} 