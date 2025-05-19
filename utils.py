import json
import os # Import os for path joining

def load_prompt_from_file(filepath):
    """Loads the prompt message structure from a JSON file.
    Handles messages with 'content' directly or via 'content_file'.
    """
    # print(f"[DEBUG] Loading prompt file: {filepath}") # Optional debug
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            prompt_messages = json.load(f)
        
        if not isinstance(prompt_messages, list):
            raise ValueError("Prompt file should contain a list of message dictionaries.")

        processed_messages = []
        base_dir = os.path.dirname(filepath) # Get directory of the JSON file
        has_content_file = False # Track if any content files were loaded

        for msg_idx, msg in enumerate(prompt_messages):
            if not isinstance(msg, dict) or 'role' not in msg:
                 raise ValueError(f"Item {msg_idx} in prompt file {filepath} must be a dictionary with a 'role' key.")

            if 'content' in msg and 'content_file' in msg:
                 raise ValueError(f"Message {msg_idx} in {filepath} cannot contain both 'content' and 'content_file': {msg}")
            
            if 'content_file' in msg:
                has_content_file = True
                content_filename = msg['content_file']
                content_filepath = os.path.join(base_dir, content_filename) # Construct path relative to JSON
                # print(f"[DEBUG]   Loading content from file: {content_filepath}") # Optional debug
                try:
                    with open(content_filepath, 'r', encoding='utf-8') as cf:
                        content_str = cf.read()
                    new_msg = msg.copy() # Avoid modifying original dict during iteration
                    new_msg['content'] = content_str
                    del new_msg['content_file']
                    processed_messages.append(new_msg)
                except FileNotFoundError:
                    raise ValueError(f"Content file '{content_filename}' not found at {content_filepath} (referenced in {filepath})")
                except Exception as e:
                    raise ValueError(f"Error reading content file '{content_filename}' at {content_filepath}: {e}")
            elif 'content' in msg:
                 if not isinstance(msg['content'], str):
                      raise ValueError(f"Message {msg_idx}'s 'content' value must be a string in {filepath}: {msg}")
                 processed_messages.append(msg.copy()) # Add message with direct content
            else:
                 raise ValueError(f"Message {msg_idx} in {filepath} must contain either 'content' or 'content_file': {msg}")
        
        # print(f"[DEBUG] Prompt file loaded successfully. Included content file: {has_content_file}") # Optional debug
        return processed_messages
    except FileNotFoundError:
        print(f"[ERROR] Prompt file not found at {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Could not decode JSON from prompt file {filepath}: {e}")
        return None
    except ValueError as e:
        print(f"[ERROR] Invalid prompt file format in {filepath}: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error loading prompt file {filepath}: {e}")
        # traceback.print_exc() # Optional
        return None


def load_airmart_context(filepath="prompts/airmart_context.json") -> str:
    """Loads Airmart context from a JSON file and formats it as a string."""
    # print(f"[DEBUG] Loading Airmart context from: {filepath}") # Optional debug
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            context_data = json.load(f)
        
        if not isinstance(context_data, dict) or "brand_context_header" not in context_data or "brand_points" not in context_data:
            raise ValueError("Context file must be a dictionary with 'brand_context_header' and 'brand_points' keys.")
        
        # Format the context into a string
        context_str = context_data["brand_context_header"] + "\n"
        context_str += "\n".join(context_data["brand_points"])
        
        # print("[DEBUG] Airmart context loaded successfully.") # Optional debug
        return context_str
    except FileNotFoundError:
        print(f"[ERROR] Airmart context file not found at {filepath}")
        return "[Error: Airmart context file not found]"
    except json.JSONDecodeError as e:
        print(f"[ERROR] Could not decode JSON from Airmart context file {filepath}: {e}")
        return "[Error: Could not decode JSON from Airmart context file]"
    except ValueError as e:
        print(f"[ERROR] Invalid context file format in {filepath}: {e}")
        return f"[Error: Invalid Airmart context file format: {e}]"
    except Exception as e:
        print(f"[ERROR] Unexpected error loading Airmart context file {filepath}: {e}")
        # traceback.print_exc() # Optional
        return f"[Error loading Airmart context: {e}]" 