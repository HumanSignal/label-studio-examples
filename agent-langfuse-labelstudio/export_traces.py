#!/usr/bin/env python3
"""
Export Langfuse Traces to Label Studio

This module handles the complete workflow for exporting agent traces from Langfuse
and importing them into Label Studio for human review and annotation.

Key Functions:
--------------
1. EXPORT LAST ANALYSIS (--export-last)
   - Read the last persisted analysis from run_agent.py
   - Get trace ID and convert to Label Studio predictions format
   - Upload to Label Studio for annotation

2. FETCH TRACES FROM LANGFUSE
   - Connect to Langfuse using API credentials from environment
   - Paginate through all available traces (or up to specified limit)
   - Each trace contains the full conversation including tool calls and responses

3. CONVERT TO LABEL STUDIO FORMAT
   - Transform traces into dialogue format or predictions format
   - Extract key fields: trace_id, PDF path, and conversation messages
   - Messages are normalized to user/assistant/tool roles

4. UPLOAD TO LABEL STUDIO
   - Connect to Label Studio using URL and API key from environment
   - Import converted traces as tasks to the specified project

Environment Variables Required:
-------------------------------
- LANGFUSE_PUBLIC_KEY: Langfuse API public key
- LANGFUSE_SECRET_KEY: Langfuse API secret key
- LANGFUSE_HOST: Langfuse host URL (optional, defaults to cloud)
- LABEL_STUDIO_URL: Label Studio instance URL
- LABEL_STUDIO_API_KEY: Label Studio API key
- LABEL_STUDIO_PROJECT_ID: Target project ID for task import

Usage Examples:
---------------
    # Export last analysis from run_agent.py to Label Studio
    python export_traces.py --export-last

    # Export traces to JSON file (default: minified dialogue format)
    python export_traces.py

    # Export in full Langfuse format
    python export_traces.py --raw

    # Export and upload to Label Studio
    python export_traces.py --upload

    # Export specific number of traces
    python export_traces.py --limit 100 --output my_traces.json

    # Upload existing JSON file to Label Studio
    python export_traces.py --upload-file traces.json

Output Format (Minified Dialogue):
----------------------------------
    [
      {
        "trace_id": "abc123",
        "pdf": "https://example.com/mortgage.pdf",
        "messages": [
          {"role": "user", "content": "Please analyze..."},
          {"role": "assistant", "content": "[Calling tool: extract_pdf_text]", "tool_name": "extract_pdf_text"},
          {"role": "tool", "content": "Document text...", "tool_name": "extract_pdf_text"},
          {"role": "assistant", "content": "Based on the analysis..."}
        ]
      }
    ]
"""

import argparse
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from label_studio_sdk.client import LabelStudio
from langfuse import get_client

# Load environment variables
load_dotenv()


# ============================================================================
# Langfuse Trace Fetching
# ============================================================================

def fetch_all_traces(langfuse, limit: int = None, batch_size: int = 50) -> list:
    """
    Fetch all traces from Langfuse using pagination.
    
    Iterates through all available traces in batches, respecting the optional
    limit parameter. Traces are returned in reverse chronological order.
    
    Args:
        langfuse: Langfuse client instance.
        limit: Maximum number of traces to fetch (None for all).
        batch_size: Number of traces to fetch per API call.
        
    Returns:
        List of Langfuse trace objects.
    """
    all_traces = []
    page = 1
    
    print(f"Fetching traces (batch size: {batch_size})...")
    
    while True:
        # Fetch a batch of traces
        response = langfuse.api.trace.list(limit=batch_size, page=page)
        traces = response.data
        
        if not traces:
            break
        
        all_traces.extend(traces)
        fetched_count = len(all_traces)
        
        print(f"  Fetched {fetched_count} traces so far...")
        
        # Check if we've reached the user-specified limit
        if limit and fetched_count >= limit:
            all_traces = all_traces[:limit]
            break
        
        # Check if we've fetched all available traces
        if len(traces) < batch_size:
            break
        
        page += 1
    
    return all_traces


def fetch_single_trace(langfuse, trace_id: str):
    """
    Fetch a single trace by ID.
    
    Args:
        langfuse: Langfuse client instance.
        trace_id: The trace ID to fetch.
        
    Returns:
        The trace object or None if not found.
    """
    try:
        return langfuse.api.trace.get(trace_id)
    except Exception as e:
        print(f"Error fetching trace {trace_id}: {e}")
        return None


def fetch_most_recent_trace(langfuse):
    """
    Fetch the most recent trace.
    
    Args:
        langfuse: Langfuse client instance.
        
    Returns:
        The most recent trace object or None.
    """
    response = langfuse.api.trace.list(limit=1, page=1)
    traces = response.data
    return traces[0] if traces else None


# ============================================================================
# Serialization Helpers
# ============================================================================

def json_serialize(obj):
    """
    Recursively convert objects to JSON-serializable types.
    
    Handles datetime objects, Pydantic models, and objects with __dict__.
    
    Args:
        obj: Any object to serialize.
        
    Returns:
        JSON-serializable version of the object.
    """
    if isinstance(obj, dict):
        return {k: json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_serialize(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, "dict"):
        return json_serialize(obj.dict())
    elif hasattr(obj, "model_dump"):
        return json_serialize(obj.model_dump())
    elif hasattr(obj, "__dict__"):
        return json_serialize(obj.__dict__)
    else:
        return obj


def trace_to_raw_dict(trace) -> dict:
    """
    Convert a Langfuse trace object to a full JSON-serializable dictionary.
    
    Preserves all trace fields for complete data export.
    
    Args:
        trace: Langfuse trace object.
        
    Returns:
        Full dictionary representation of the trace.
    """
    if hasattr(trace, "dict"):
        trace_dict = trace.dict()
    elif hasattr(trace, "model_dump"):
        trace_dict = trace.model_dump()
    else:
        trace_dict = {
            "id": getattr(trace, "id", None),
            "name": getattr(trace, "name", None),
            "timestamp": getattr(trace, "timestamp", None),
            "user_id": getattr(trace, "user_id", None),
            "session_id": getattr(trace, "session_id", None),
            "input": getattr(trace, "input", None),
            "output": getattr(trace, "output", None),
            "metadata": getattr(trace, "metadata", None),
            "tags": getattr(trace, "tags", None),
            "version": getattr(trace, "version", None),
            "release": getattr(trace, "release", None),
            "public": getattr(trace, "public", None),
            "latency": getattr(trace, "latency", None),
            "total_cost": getattr(trace, "total_cost", None),
            "observations": getattr(trace, "observations", None),
            "scores": getattr(trace, "scores", None),
        }
    
    return json_serialize(trace_dict)


# ============================================================================
# Dialogue Conversion Helpers
# ============================================================================

def extract_message_content(msg: dict) -> str:
    """
    Extract text content from a message object.
    
    Handles various content formats including strings, lists, and
    multi-part messages with text and tool use components.
    
    Args:
        msg: Message dictionary.
        
    Returns:
        Extracted text content as string.
    """
    content = msg.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle multi-part content (text, images, etc.)
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    parts.append(f"[Tool: {part.get('name', 'unknown')}]")
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts)
    return str(content)


def normalize_role(role_or_type: str) -> str:
    """
    Normalize message role/type to standard values: user|assistant|tool|system.
    
    Args:
        role_or_type: Raw role string from the trace.
        
    Returns:
        Normalized role string.
    """
    role = role_or_type.lower() if role_or_type else "unknown"
    if role in ("human", "user"):
        return "user"
    elif role in ("ai", "assistant", "aimessage"):
        return "assistant"
    elif role in ("tool", "function", "tool_result"):
        return "tool"
    elif role == "system":
        return "system"
    return role


def extract_pdf_path(messages: list) -> Optional[str]:
    """
    Extract the PDF filepath or URL from conversation messages.
    
    Searches through messages for .pdf paths or URLs.
    
    Args:
        messages: List of message dictionaries.
        
    Returns:
        PDF path/URL if found, None otherwise.
    """
    pdf_pattern = r'([^\s"\']+\.pdf)'
    
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        
        # Check message content
        content = msg.get("content", "")
        if isinstance(content, str):
            match = re.search(pdf_pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
    
    return None


def trace_to_dialogue(trace) -> dict:
    """
    Convert a Langfuse trace to a minified dialogue format for Label Studio.
    
    Extracts the conversation from the trace, including:
    - User messages
    - Assistant responses  
    - Tool calls (with name and arguments)
    - Tool results
    
    Args:
        trace: Langfuse trace object.
        
    Returns:
        Dictionary with trace_id, pdf path, and messages array.
    """
    trace_dict = json_serialize(trace_to_raw_dict(trace))
    trace_id = trace_dict.get("id", "unknown")
    
    messages = []
    seen_ids = set()  # Avoid duplicate messages
    
    # Extract messages from output (contains the full conversation)
    output = trace_dict.get("output", {})
    if isinstance(output, dict):
        output_messages = output.get("messages", [])
    else:
        output_messages = []
    
    # If no messages in output, try input
    if not output_messages:
        input_data = trace_dict.get("input", {})
        if isinstance(input_data, dict):
            output_messages = input_data.get("messages", [])
    
    # Extract PDF path from messages
    pdf_path = extract_pdf_path(output_messages)
    
    for msg in output_messages:
        if not isinstance(msg, dict):
            continue
        
        # Get message ID to avoid duplicates
        msg_id = msg.get("id")
        if msg_id and msg_id in seen_ids:
            continue
        if msg_id:
            seen_ids.add(msg_id)
        
        # Determine role
        role_raw = msg.get("role") or msg.get("type", "")
        role = normalize_role(role_raw)
        
        # Skip empty AI messages (tool call placeholders)
        content = extract_message_content(msg)
        
        # Handle tool calls in assistant messages
        tool_calls = msg.get("tool_calls") or msg.get("additional_kwargs", {}).get("tool_calls", [])
        
        if tool_calls and not content:
            # Assistant message with tool calls but no text content
            for tc in tool_calls:
                tool_name = tc.get("name") or (tc.get("function", {}).get("name"))
                tool_args = tc.get("args") or tc.get("function", {}).get("arguments", "")
                if isinstance(tool_args, dict):
                    tool_args = json.dumps(tool_args)
                messages.append({
                    "role": "assistant",
                    "content": f"[Calling tool: {tool_name}]",
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                })
        elif role == "tool":
            # Tool response message
            tool_name = msg.get("name") or msg.get("tool_name", "")
            message_entry = {
                "role": "tool",
                "content": content,
            }
            if tool_name:
                message_entry["tool_name"] = tool_name
            messages.append(message_entry)
        elif content or role == "assistant":
            # Regular user/assistant message with content
            messages.append({
                "role": role,
                "content": content,
            })
    
    return {
        "trace_id": trace_id,
        "pdf": pdf_path,
        "messages": messages,
    }


# ============================================================================
# Label Studio Integration
# ============================================================================

# Path to persist the last analysis result
LAST_ANALYSIS_FILE = Path(__file__).parent / ".last_analysis.json"


def to_label_studio_predictions(
    analysis: dict,
    pdf_path: str,
    trace_id: str = None,
    messages: list = None,
    model_version: str = "1.0",
) -> dict:
    """
    Convert a MortgageAnalysisResult dict to Label Studio predictions format.
    
    Each field is translated to a prediction item with appropriate type:
    - numbers -> "number"
    - strings -> "textarea" 
    - enums/choices -> "choices"
    
    Args:
        analysis: The structured mortgage analysis result as a dict.
        pdf_path: Path to the PDF that was analyzed.
        trace_id: Langfuse trace ID for this analysis.
        messages: Conversation messages from the agent.
        model_version: Version identifier for the model.
        
    Returns:
        Label Studio compatible predictions dict with data containing
        pdf, trace_id, and messages.
    """
    result_items = []
    
    def add_field(from_name: str, value, field_type: str, to_name: str = "pdf"):
        """Add a field to the result items."""
        if value is None:
            return
            
        item = {
            "id": str(uuid.uuid4())[:8],
            "from_name": from_name,
            "to_name": to_name,
            "type": field_type,
        }
        
        if field_type == "number":
            item["value"] = {"number": value}
        elif field_type == "textarea":
            item["value"] = {"text": [str(value)]}
        elif field_type == "choices":
            item["value"] = {"choices": [str(value)]}
        
        result_items.append(item)
    
    # Loan Summary fields
    ls = analysis.get("loan_summary", {})
    add_field("loan_amount", ls.get("loan_amount"), "number")
    add_field("currency", ls.get("currency"), "textarea")
    add_field("loan_term_years", ls.get("loan_term_years"), "number")
    add_field("interest_rate_type", ls.get("interest_rate_type"), "choices")
    add_field("interest_rate_percent", ls.get("interest_rate_percent"), "number")
    add_field("comparison_rate_or_APR_percent", ls.get("comparison_rate_or_APR_percent"), "number")
    add_field("monthly_payment_amount", ls.get("monthly_payment_amount"), "number")
    add_field("estimated_LTV_ratio", ls.get("estimated_LTV_ratio"), "number")
    
    # Market Snapshot fields
    ms = analysis.get("market_snapshot", {})
    add_field("region", ms.get("region"), "textarea")
    add_field("data_as_of_date", ms.get("data_as_of_date"), "textarea")
    add_field("typical_fixed_rate_percent", ms.get("typical_fixed_rate_percent"), "number")
    add_field("typical_variable_rate_percent", ms.get("typical_variable_rate_percent"), "number")
    add_field("typical_APR_percent", ms.get("typical_APR_percent"), "number")
    
    # Comparison Result fields
    cr = analysis.get("comparison_result", {})
    add_field("rate_position_vs_market", cr.get("rate_position_vs_market"), "choices")
    add_field("estimated_savings_or_cost_difference_comment", cr.get("estimated_savings_or_cost_difference_comment"), "textarea")
    
    # Top-level fields
    add_field("recommendation", analysis.get("recommendation"), "textarea")
    add_field("notes", analysis.get("notes"), "textarea")
    
    return {
        "data": {
            "pdf": pdf_path,
            "trace_id": trace_id,
            "messages": messages,
        },
        "predictions": [
            {
                "model_version": model_version,
                "result": result_items,
            }
        ],
    }


def load_last_analysis() -> Optional[dict]:
    """
    Load the last persisted analysis result from the filesystem.
    
    Returns:
        The analysis dict if found, None otherwise.
    """
    if not LAST_ANALYSIS_FILE.exists():
        return None
    
    with open(LAST_ANALYSIS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def export_last_analysis_to_label_studio(project_id: str = None) -> dict:
    """
    Export the last analysis to Label Studio.
    
    Reads the persisted analysis, fetches the trace from Langfuse,
    converts to predictions format, and uploads to Label Studio.
    
    Args:
        project_id: Label Studio project ID (or from env).
        
    Returns:
        Dict with success status and label_studio_url or error.
    """
    # Load the last analysis
    last_analysis = load_last_analysis()
    if not last_analysis:
        return {
            "success": False,
            "error": "No analysis found. Run an analysis first.",
        }
    
    trace_id = last_analysis.get("trace_id")
    pdf_url = last_analysis.get("pdf_url")
    analysis_json = last_analysis.get("analysis_json")
    messages = last_analysis.get("messages", [])
    
    if not trace_id or not pdf_url:
        return {
            "success": False,
            "error": "Invalid analysis data. Run a new analysis.",
        }
    
    # Convert to Label Studio predictions format
    predictions = to_label_studio_predictions(
        analysis=analysis_json,
        pdf_path=pdf_url,
        trace_id=trace_id,
        messages=messages,
    )
    
    # Use predictions as the task (it already has the data field)
    task = predictions
    
    # Get project ID from env if not provided
    project_id = project_id or os.getenv("LABEL_STUDIO_PROJECT_ID")
    
    # Upload to Label Studio
    upload_to_label_studio([task], project_id=project_id)
    
    # Return success with Label Studio URL
    ls_url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8001")
    label_studio_url = f"{ls_url}/projects/{project_id}"
    
    return {
        "success": True,
        "label_studio_url": label_studio_url,
    }


def dialogue_to_label_studio_task(dialogue: dict) -> dict:
    """
    Convert a dialogue dictionary to Label Studio task format.
    
    Creates a task with the PDF URL and conversation messages as data fields.
    
    Args:
        dialogue: Dictionary from trace_to_dialogue().
        
    Returns:
        Label Studio task dictionary.
    """
    return {
        "data": {
            "pdf": dialogue.get("pdf"),
            "trace_id": dialogue.get("trace_id"),
            "messages": dialogue.get("messages", []),
        }
    }


def upload_to_label_studio(
    tasks: list,
    project_id: str = None,
    ls_url: str = None,
    ls_api_key: str = None,
) -> list:
    """
    Upload tasks to Label Studio project.
    
    Args:
        tasks: List of Label Studio task dictionaries.
        project_id: Label Studio project ID (or from LABEL_STUDIO_PROJECT_ID env).
        ls_url: Label Studio URL (or from LABEL_STUDIO_URL env).
        ls_api_key: Label Studio API key (or from LABEL_STUDIO_API_KEY env).
        
    Returns:
        The uploaded tasks.
        
    Raises:
        ValueError: If required configuration is missing.
    """
    ls_url = ls_url or os.getenv("LABEL_STUDIO_URL")
    ls_api_key = ls_api_key or os.getenv("LABEL_STUDIO_API_KEY")
    project_id = project_id or os.getenv("LABEL_STUDIO_PROJECT_ID")
    
    if not all([ls_url, ls_api_key, project_id]):
        raise ValueError(
            "Missing Label Studio configuration. Required: "
            "LABEL_STUDIO_URL, LABEL_STUDIO_API_KEY, LABEL_STUDIO_PROJECT_ID"
        )
    
    ls = LabelStudio(base_url=ls_url, api_key=ls_api_key)
    ls.projects.import_tasks(id=int(project_id), request=tasks)
    
    print(f"Uploaded {len(tasks)} tasks to Label Studio project {project_id}")
    return tasks


def export_traces_to_label_studio(
    limit: int = None,
    project_id: str = None,
) -> list:
    """
    Complete workflow: fetch traces from Langfuse and upload to Label Studio.
    
    Args:
        limit: Maximum number of traces to export.
        project_id: Label Studio project ID.
        
    Returns:
        List of uploaded tasks.
    """
    # Initialize Langfuse
    langfuse = get_client()
    if not langfuse.auth_check():
        raise RuntimeError("Failed to authenticate with Langfuse")
    
    # Fetch traces
    traces = fetch_all_traces(langfuse, limit=limit)
    if not traces:
        print("No traces found to export.")
        return []
    
    # Convert to dialogues and then to Label Studio tasks
    dialogues = [trace_to_dialogue(trace) for trace in traces]
    tasks = [dialogue_to_label_studio_task(d) for d in dialogues]
    
    # Upload to Label Studio
    return upload_to_label_studio(tasks, project_id=project_id)


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Export Langfuse traces and upload to Label Studio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python export_traces.py                        # Export to JSON file
    python export_traces.py --raw                  # Full Langfuse format
    python export_traces.py --upload               # Export and upload to LS
    python export_traces.py --upload-file traces.json  # Upload existing file
    python export_traces.py --limit 100 -o my_traces.json
        """,
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output JSON file path. Defaults to 'traces_<timestamp>.json'.",
    )
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Maximum number of traces to export. Defaults to all traces.",
    )
    
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=50,
        help="Number of traces to fetch per API call. Default: 50.",
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Export in full Langfuse format instead of minified dialogue format.",
    )
    
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload exported traces to Label Studio.",
    )
    
    parser.add_argument(
        "--upload-file",
        type=str,
        default=None,
        help="Upload an existing JSON file to Label Studio instead of fetching traces.",
    )
    
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Label Studio project ID (overrides LABEL_STUDIO_PROJECT_ID env).",
    )
    
    parser.add_argument(
        "--export-last",
        action="store_true",
        help="Export the last analysis (from run_agent.py) to Label Studio.",
    )
    
    args = parser.parse_args()
    
    # Handle export-last mode (export last analysis from run_agent.py)
    if args.export_last:
        print("Exporting last analysis to Label Studio...")
        result = export_last_analysis_to_label_studio(project_id=args.project_id)
        
        if result["success"]:
            print(f"Successfully exported to Label Studio!")
            print(f"Open: {result['label_studio_url']}")
            return 0
        else:
            print(f"Error: {result['error']}")
            return 1
    
    # Handle upload-file mode (upload existing file without fetching)
    if args.upload_file:
        print(f"Loading traces from {args.upload_file}...")
        with open(args.upload_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Handle both list format and dict with "traces" key
        if isinstance(data, dict) and "traces" in data:
            dialogues = data["traces"]
        elif isinstance(data, list):
            dialogues = data
        else:
            print("Error: Invalid file format. Expected list or dict with 'traces' key.")
            return 1
        
        # Convert to Label Studio tasks if needed
        tasks = []
        for item in dialogues:
            if "data" in item:
                # Already in LS format
                tasks.append(item)
            else:
                # Convert from dialogue format
                tasks.append(dialogue_to_label_studio_task(item))
        
        upload_to_label_studio(tasks, project_id=args.project_id)
        return 0
    
    # Initialize Langfuse client
    print("Initializing Langfuse client...")
    langfuse = get_client()
    
    # Verify connection
    if not langfuse.auth_check():
        print("Error: Failed to authenticate with Langfuse.")
        print("Please check your LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.")
        return 1
    
    print("Connected to Langfuse successfully.")
    
    # Fetch all traces
    traces = fetch_all_traces(
        langfuse,
        limit=args.limit,
        batch_size=args.batch_size,
    )
    
    if not traces:
        print("No traces found.")
        return 0
    
    print(f"\nTotal traces fetched: {len(traces)}")
    
    # Convert traces based on format
    if args.raw:
        print("Converting traces to raw Langfuse format...")
        traces_data = [trace_to_raw_dict(trace) for trace in traces]
    else:
        print("Converting traces to minified dialogue format...")
        traces_data = [trace_to_dialogue(trace) for trace in traces]
    
    # Generate output filename if not specified
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"traces_{timestamp}.json")
    
    # Write to JSON file (minified by default, pretty for raw)
    print(f"Writing traces to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        if args.raw:
            json.dump(
                {
                    "exported_at": datetime.now().isoformat(),
                    "total_traces": len(traces_data),
                    "traces": traces_data,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        else:
            # Minified output for dialogue format
            json.dump(traces_data, f, ensure_ascii=False, separators=(",", ":"))
    
    print(f"\nExport complete!")
    print(f"  Output file: {output_path}")
    print(f"  Total traces: {len(traces_data)}")
    print(f"  Format: {'raw Langfuse' if args.raw else 'minified dialogue'}")
    
    # Upload to Label Studio if requested
    if args.upload:
        print("\nUploading to Label Studio...")
        tasks = [dialogue_to_label_studio_task(d) for d in traces_data]
        upload_to_label_studio(tasks, project_id=args.project_id)
    
    return 0


if __name__ == "__main__":
    exit(main())
