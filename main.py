# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import sys
import traceback
import openai

# Import configurations and validate
import config
try:
    config.validate_config()
except ValueError as e:
    print(f"[ERROR] Configuration validation failed: {e}")
    sys.exit(1) # Exit if config is invalid

# Import core components
from ai_services import AIService
from reviewers import ConsoleReviewer
from storage import FileStorage
from workflow import ContentWorkflow
from scheduler import WorkflowScheduler

def main():
    """Initializes and runs the AI Social Media Post Generator."""
    print("\n[INFO] === Starting AI Social Media Post Generator ===")

    try:
        # 1. Initialize Services
        print("[INFO] Initializing services...")
        ai_service = AIService(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            generation_model=config.MODEL_ID,
            review_model=config.REVIEW_MODEL_ID
        )
        reviewer = ConsoleReviewer() # Using console reviewer
        storage = FileStorage(output_dir=config.OUTPUT_DIR)

        # 2. Initialize Workflow
        print("[INFO] Initializing workflow...")
        # News fetcher function is imported/defined in workflow.py
        content_workflow = ContentWorkflow(
            ai_service=ai_service,
            reviewer=reviewer,
            storage=storage,
            # Can override other config params here if needed, e.g.:
            # max_regen_attempts=2,
            # human_review_required_post=False
        )

        # 3. Initialize Scheduler
        print("[INFO] Initializing scheduler...")
        scheduler = WorkflowScheduler(workflow=content_workflow)

        # 4. Run initial job immediately
        scheduler.run_once()

        # 5. Start the recurring schedule
        scheduler.start_schedule(schedule_day=config.SCHEDULE_DAY, schedule_time=config.SCHEDULE_TIME)

    except ImportError as e:
         print(f"\n[ERROR] Import Error: {e}")
         print("[ERROR] Please ensure all required modules (config.py, ai_services.py, etc.) exist and dependencies are installed.")
         traceback.print_exc()
         sys.exit(1)
    except openai.AuthenticationError as e: # Specific handling for auth error on init
         print(f"\n[ERROR] OpenAI Authentication Error during initialization: {e}")
         print("[ERROR] Please check your OPENAI_API_KEY in the .env file or environment variables.")
         sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred during setup or execution: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
