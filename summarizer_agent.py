import os
from openai import OpenAI, OpenAIError

def summarize_with_llm(client: OpenAI, text_to_summarize: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Summarizes the given text using the specified OpenAI model and client.

    Args:
        client (OpenAI): An initialized OpenAI client instance.
        text_to_summarize (str): The text content to summarize.
        model (str): The OpenAI model ID to use for summarization.

    Returns:
        str: The summarized text, or an error message if summarization fails.
    """
    if not client:
        # This check might be redundant if the caller ensures client is valid, but safe to keep.
        print("[ERROR] Summarization called with invalid OpenAI client.")
        return "[Error: Invalid OpenAI client provided.]"
    if not text_to_summarize:
        print("[WARN] Summarization called with no text to summarize.")
        return "[Error: No text provided for summarization.]"

    print(f"[INFO] ---> Attempting summarization with {model}...")
    # print(f"[DEBUG] Text to summarize (Preview): {text_to_summarize[:200]}...") # Optional debug

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to summarize news articles concisely. Focus on the key information relevant to small businesses, creators, and e-commerce trends."},
                {"role": "user", "content": f"""Please summarize the following article text to one paragraph short and clear and concise but with all the important information:

{text_to_summarize}"""}
            ],
            temperature=0.5,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        summary = response.choices[0].message.content.strip()
        print(f"[INFO] <--- Summarization successful ({model}). Length: {len(summary)}")
        return f"[LLM Summary]: {summary}"
    except OpenAIError as e:
        print(f"[ERROR] An OpenAI API error occurred during summarization ({model}): {e}")
        return f"[Error summarizing text: {e}]"
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during summarization ({model}): {e}")
        # traceback.print_exc() # Optionally add traceback here if needed
        return f"[Unexpected error summarizing text: {e}]"
