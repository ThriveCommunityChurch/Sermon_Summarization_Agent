from typing import Annotated, TypedDict
from langgraph.graph import MessagesState


class AgentState(TypedDict):
    """
    State for the Sermon Summarization Agent.
    
    Attributes:
        messages: LangGraph messages state for agent communication
        filePath: Path to the sermon audio/video file being processed
        transcription: Full transcription text from Whisper
        transcription_path: Path to the transcription.txt file
        segments_path: Path to the transcription_segments.json file
        summary: Generated summary text
        summary_path: Path to the summary.txt file
    """
    messages: MessagesState
    filePath: Annotated[str, "The file path of the sermon file being transcribed"]
    transcription: Annotated[str, "Full transcription text from Whisper"]
    transcription_path: Annotated[str, "Path to transcription.txt file"]
    segments_path: Annotated[str, "Path to transcription_segments.json file"]
    summary: Annotated[str, "Generated summary of the sermon"]
    summary_path: Annotated[str, "Path to summary.txt file"]

