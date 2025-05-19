import schedule
import time
import traceback
from workflow import ContentWorkflow # Import the workflow class

class WorkflowScheduler:
    """Handles scheduling and running the content generation workflow."""

    def __init__(self, workflow: ContentWorkflow):
        self.workflow = workflow
        print("[INFO] WorkflowScheduler initialized.")

    def _job(self):
        """Defines the job to be executed by the scheduler."""
        job_start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[INFO] === Running Scheduled Job === [Start Time: {job_start_time}]")
        try:
            # Run workflow - languages are now handled internally based on config
            self.workflow.run()

            # Optional: Run workflow for Chinese/China (uncomment if needed)
            # print("[INFO] --- Running Scheduled Job for zh/CN ---") # Example if uncommented

        except Exception as e:
            print(f"[ERROR] !!! Critical error during scheduled job execution: {e} !!!")
            traceback.print_exc()
        finally:
             job_end_time = time.strftime('%Y-%m-%d %H:%M:%S')
             print(f"[INFO] === Scheduled Job Finished === [End Time: {job_end_time}]")

    def run_once(self):
        """Runs the workflow job immediately."""
        print("[INFO] ---> Running initial job now...")
        self._job()
        print("[INFO] <--- Initial job finished.")

    def start_schedule(self, schedule_day="monday", schedule_time="09:00"):
        """Sets up and starts the recurring schedule."""
        print(f"[INFO] Setting up weekly schedule: Every {schedule_day.capitalize()} at {schedule_time}")
        schedule.every().monday.at(schedule_time).do(self._job)
        # TODO: Make schedule_day dynamic (e.g., schedule.every().__getattribute__(schedule_day).at...)
        # This requires careful handling of the schedule library's API.

        print("[INFO] Scheduler started. Waiting for next run... (Press Ctrl+C to stop)")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60) # Check every minute
        except KeyboardInterrupt:
            print("\n[INFO] Scheduler stopped by user.") 