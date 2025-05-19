import os
import json
import time
from typing import Dict, Any, Set, List, Optional
import urllib.request
import urllib.parse
import shutil # To save the downloaded file

class FileStorage:
    """Handles saving generated content and downloading associated images."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"[INFO] FileStorage initialized. Output directory: {self.output_dir}")

    def save_content(self, platform_name: str, language: str, content: Dict[str, Any], image_url: Optional[str] = None):
        """
        Saves the approved content to a timestamped JSON file.
        If an image_url is provided, attempts to download the image and save it locally,
        storing the relative path in the JSON.
        """
        if not content:
            print("[WARN] Attempted to save empty content. Skipping.")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"{platform_name.lower()}_post_{language}_{timestamp}"
        json_filename = os.path.join(self.output_dir, f"{base_filename}.json")

        save_data = content.copy()
        image_status = "without image" # Default status

        if image_url:
            save_data['image_prompt_used'] = content.get('image_prompt') # Keep track of the prompt
            save_data['original_image_url'] = image_url # Store original URL for reference

            try:
                # Attempt to determine image extension from URL
                parsed_url = urllib.parse.urlparse(image_url)
                path_part = parsed_url.path
                _, ext = os.path.splitext(path_part)
                if not ext:
                    print(f"[WARN] Could not determine image extension from URL: {image_url}. Defaulting to .jpg")
                    ext = '.jpg' # Default extension

                image_filename = f"{base_filename}{ext}"
                image_filepath = os.path.join(self.output_dir, image_filename)

                print(f"[INFO] Attempting to download image from {image_url} to {image_filepath}...")
                # Download the image
                with urllib.request.urlopen(image_url) as response, open(image_filepath, 'wb') as out_file:
                    # Check if the response status is OK
                    if response.getcode() == 200:
                        shutil.copyfileobj(response, out_file)
                        save_data['saved_image_path'] = image_filename # Store relative path
                        image_status = f"with image saved to {image_filename}"
                        print(f"[INFO] Successfully downloaded and saved image: {image_filename}")
                    else:
                         print(f"[WARN] Failed to download image: HTTP status {response.getcode()}")
                         image_status = f"with image URL (download failed: HTTP {response.getcode()})"

            except urllib.error.URLError as e:
                print(f"[WARN] Failed to download image from {image_url}: URL Error {e.reason}")
                image_status = f"with image URL (download failed: {e.reason})"
            except Exception as e:
                print(f"[WARN] Error downloading or saving image from {image_url}: {e}")
                image_status = f"with image URL (download failed: {e})"
                # Optionally remove the partially downloaded file if it exists
                if os.path.exists(image_filepath):
                    try: os.remove(image_filepath)
                    except OSError: pass # Ignore errors removing file

        try:
            print(f"[INFO] Saving {platform_name} ({language}) post metadata to {json_filename}...")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
            # Updated status message
            print(f"[INFO] Successfully saved {platform_name} ({language}) post metadata ({image_status}) to {json_filename}")
        except Exception as e:
            print(f"[ERROR] Error saving {platform_name} ({language}) post metadata to {json_filename}: {e}")

    # --- Methods for Handling Used Article Links ---

    def _get_used_links_filepath(self) -> str:
        """Returns the path to the file storing used article links."""
        return os.path.join(self.output_dir, "used_article_links.txt")

    def load_used_article_links(self) -> Set[str]:
        """Loads the set of previously used article URLs from the storage file."""
        used_links_file = self._get_used_links_filepath()
        used_links: Set[str] = set()
        print(f"[INFO] Loading used article links from: {used_links_file}")
        if os.path.exists(used_links_file):
            try:
                with open(used_links_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        link = line.strip()
                        if link: # Avoid adding empty lines
                            used_links.add(link)
                print(f"[INFO] Loaded {len(used_links)} used article links.")
            except Exception as e:
                print(f"[WARN] Could not load used article links from {used_links_file}: {e}")
        else:
            print(f"[INFO] Used article links file not found ({used_links_file}). Starting with an empty set.")
        return used_links

    def append_used_article_links(self, new_links: List[str]):
        """Appends newly used article URLs to the storage file."""
        if not new_links:
            print("[INFO] No new article links provided to append.")
            return

        used_links_file = self._get_used_links_filepath()
        print(f"[INFO] Appending {len(new_links)} new links to {used_links_file}...")
        try:
            # Append mode ensures we don't overwrite existing links
            with open(used_links_file, 'a', encoding='utf-8') as f:
                count = 0
                for link in new_links:
                    if link and link != '#': # Ensure we have a valid link
                        f.write(link + '\n')
                        count += 1
            print(f"[INFO] Successfully appended {count} new links.")
        except Exception as e:
            print(f"[ERROR] Error appending used article links to {used_links_file}: {e}") 