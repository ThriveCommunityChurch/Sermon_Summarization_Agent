import os
import json
from pathlib import Path
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from classes.agent_state import AgentState


def _load_transcription() -> str:
    """Load the transcription text from transcription.txt file."""
    txt_path = Path("transcription.txt")
    if not txt_path.exists():
        raise FileNotFoundError(
            "No transcription found. Run transcribe_audio first to generate transcription.txt"
        )
    
    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("Transcription file is empty. Please ensure transcription completed successfully.")
    
    return text


@tool
def summarize_sermon(state: AgentState):
    """
    Generate a single-paragraph, end-user-friendly summary of the sermon. 
    
    Uses GPT-4o-mini to analyze the transcription and create a concise summary
    that captures the sermon's core message and overall purpose.
    
    Reads:
    - transcription.txt (full transcription text)
    
    Writes:
    - summary.txt (single paragraph summary)
    - summary.json (summary with metadata)
    
    Returns a JSON string with keys: {"summary", "summary_path", "metadata_path"}.
    """
    # Load the transcription
    transcription = _load_transcription()
    
    # Initialize GPT-4o-mini for summarization
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    # Create the system prompt for summarization
    system_prompt = (
        "You are an expert at summarizing sermons for church audiences. "
        "Your task is to create a single-paragraph summary that captures what listeners will learn, "
        "experience, and take away from the sermon—not just a retelling of its content in a summarization. Focus on the "
        "insights, transformations, and practical wisdom available to those who engage with the message. "
        "\n\n"
        "Requirements:\n"
        "- Write for listeners of the sermon—as if speaking directly to them. Your tone should be conversational, invitational, and spiritually engaging\n"
        "- The summary must be a single paragraph (no line breaks within the summary)\n"
        "- The summary should be no more than 120 words maximum. Less is better if you can effectively communicate the core message\n"
        "- Use an opening question only if the sermon explicitly challenges behavior or worldview—otherwise, open with a statement that draws curiosity or empathy.\n"
        "- Frame the summary around what listeners will discover, learn, or be challenged by—not just what the sermon is about\n"
        "- Base your summary on what is explicitly or clearly implied in the transcription, without adding unstated ideas\n"
        "- DO NOT mention the church name, organization name, or pastor's name\n"
        "- DO NOT cite specific passage references directly (e.g., 'Matthew 2:1-12') unless the entire sermon is an exposition of a single passage\n"
        "- Vary your opening approach—avoid using the same opening verb or structure repeatedly. Use diverse, engaging starts that feel natural and specific to each sermon's unique message"
        "\n\n"
        "Guidelines:\n"
        "- Avoid using phrases like 'in this sermon...', 'in this message...', or other generic introductions that can get repetitive when a listener is viewing multiple summaries\n"
        "- Use language that helps listeners imagine themselves benefiting from the message using diverse, engaging and thought provoking language that feels natural and specific to each sermon's unique message\n"
        "- Focus on the transformation, insight, or practical wisdom the sermon offers\n"
        "- Capture the sermon's emotional tone and spiritual purpose\n"
        "- Be concise and punchy, avoiding dense or overly packed sentences\n"
        "- Keep sentences short and clear; if a sentence has multiple clauses, consider breaking the idea into simpler parts\n"
        "- Write to inform laypeople, not academics—content should be accessible but substantive\n"
        "- Write in an engaging tone that reflects the sermon's spirit and makes people want to listen\n"
        "- Balance accessibility with theological substance—explain concepts naturally without dumbing down\n"
        "- End with a closing sentence, or final insight or question that leaves the listener reflecting—avoid generic wrap-ups or repeating earlier phrases\n"
        "- Prioritize clarity, readability, and relatability for everyday people over religious jargon\n"
        "- Avoid simply retelling biblical stories or sermon content—focus on the takeaway and application\n"
        "- Reflect the emotional temperature of the sermon (e.g., convicting, comforting, celebratory, urgent) so each summary feels true to its heart\n"
        "- You may use light metaphor or imagery only when it directly reflects the sermon's expressed themes, not when inventing new symbolic language."
    )
    
    user_prompt = (
        f"Please summarize the following sermon transcription into a single paragraph "
        f"that captures its core message and purpose:\n\n{transcription}"
    )
    
    # Generate the summary
    print("Generating sermon summary with GPT-4o-mini...")
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    
    summary_text = response.content.strip()
    
    # Ensure it's a single paragraph (remove any internal line breaks)
    summary_text = " ".join(summary_text.split("\n"))
    
    # Write outputs
    output_txt = Path("summary.txt")
    output_json = Path("summary.json")
    
    # Save plain text summary
    output_txt.write_text(summary_text, encoding="utf-8")
    
    # Save JSON with metadata
    metadata = {
        "summary": summary_text,
        "word_count": len(summary_text.split()),
        "character_count": len(summary_text),
        "model": "gpt-4o-mini",
        "transcription_length": len(transcription),
    }
    
    output_json.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"Summary generated successfully ({metadata['word_count']} words)")
    print(f"Summary saved to: {output_txt.resolve()}")
    
    # Return result
    result = {
        "summary": summary_text,
        "summary_path": str(output_txt.resolve()),
        "metadata_path": str(output_json.resolve()),
    }
    
    return json.dumps(result)