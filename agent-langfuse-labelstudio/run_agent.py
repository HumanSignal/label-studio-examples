#!/usr/bin/env python3
"""
Mortgage Offer Comparison Agent

A minimalist agent that analyzes mortgage/loan offer documents and compares 
them to current market conditions using LangGraph, pymupdf, and Google Custom Search.

Workflow:
---------
1. DOCUMENT INGESTION
   - Accept a PDF file path or URL as input
   - If URL provided, download PDF to temporary location
   - Extract text content from PDF using pymupdf

2. MARKET RESEARCH
   - Determine the region/country from the document or user input
   - Search for current mortgage rates in that region using Google Custom Search
   - Gather typical fixed, variable, and APR rates for comparison

3. ANALYSIS & COMPARISON
   - Extract key loan terms: amount, rate, term, monthly payment, LTV
   - Compare offer rates against current market conditions
   - Categorize as better/similar/worse than market
   - Generate recommendation and notes

4. OUTPUT GENERATION
   - Produce structured JSON analysis (MortgageAnalysisResult)
   - Convert to Label Studio predictions format for annotation
   - Log trace to Langfuse for observability

5. TRACE LOGGING
   - All agent interactions are automatically logged to Langfuse
   - Traces can later be exported via export_traces.py

Environment Variables Required:
-------------------------------
- OPENAI_API_KEY: OpenAI API key for GPT-4
- GOOGLE_API_KEY: Google API key for Custom Search
- GOOGLE_CSE_ID: Google Custom Search Engine ID
- LANGFUSE_PUBLIC_KEY: Langfuse public key for tracing
- LANGFUSE_SECRET_KEY: Langfuse secret key for tracing
- LANGFUSE_HOST: Langfuse host URL (optional)

Usage Examples:
---------------
    # Analyze a local PDF
    python run_agent.py test_data/loan_simulations/example.pdf

    # Analyze with explicit region
    python run_agent.py document.pdf --region Portugal

    # Analyze from URL
    python run_agent.py https://example.com/mortgage.pdf --region Germany

    # Custom trace name for Langfuse
    python run_agent.py document.pdf --trace-name "customer-123-offer"

    # Skip automatic file export
    python run_agent.py document.pdf --no-export

Output Files (when not using --no-export):
------------------------------------------
    - analysis_<timestamp>.json: Structured JSON analysis
    - predictions_<timestamp>.json: Label Studio predictions format
"""

import argparse
import json
import os
import sys
import tempfile
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal, Optional

import pymupdf
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Path to persist the last analysis result (shared with export_traces.py)
LAST_ANALYSIS_FILE = Path(__file__).parent / ".last_analysis.json"


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class LoanSummary(BaseModel):
    """Summary of the loan offer extracted from the document."""
    loan_amount: Optional[float] = Field(None, description="Total principal amount borrowed")
    currency: Optional[str] = Field(None, description="Currency code (e.g., USD, EUR, GBP)")
    loan_term_years: Optional[int] = Field(None, description="Length of the mortgage in years")
    interest_rate_type: Optional[Literal["fixed", "variable", "mixed", "unknown"]] = Field(
        None, description="Type of interest rate"
    )
    interest_rate_percent: Optional[float] = Field(None, description="Current nominal rate as percentage")
    comparison_rate_or_APR_percent: Optional[float] = Field(
        None, description="APR / TAEG / comparison rate as percentage"
    )
    monthly_payment_amount: Optional[float] = Field(None, description="Current required monthly payment")
    estimated_LTV_ratio: Optional[float] = Field(None, description="Loan-to-Value ratio if calculable")


class MarketSnapshot(BaseModel):
    """Current market conditions for the mortgage region."""
    region: Optional[str] = Field(None, description="Country or market of the mortgage")
    data_as_of_date: Optional[str] = Field(None, description="Date of market data (YYYY-MM-DD)")
    typical_fixed_rate_percent: Optional[float] = Field(None, description="Typical fixed mortgage rate")
    typical_variable_rate_percent: Optional[float] = Field(None, description="Typical variable mortgage rate")
    typical_APR_percent: Optional[float] = Field(None, description="Typical APR/comparison rate")


class ComparisonResult(BaseModel):
    """Comparison of the offer against market conditions."""
    rate_position_vs_market: Optional[Literal[
        "better_than_market", "similar_to_market", "worse_than_market", "unknown"
    ]] = Field(None, description="How the offer compares to market rates")
    estimated_savings_or_cost_difference_comment: Optional[str] = Field(
        None, description="Brief comment on savings or additional cost"
    )


class MortgageAnalysisResult(BaseModel):
    """Complete mortgage analysis output."""
    loan_summary: LoanSummary = Field(description="Summary of extracted loan terms")
    market_snapshot: MarketSnapshot = Field(description="Current market conditions")
    comparison_result: ComparisonResult = Field(description="Comparison against market")
    recommendation: Optional[str] = Field(None, description="Short guidance in 1-3 sentences")
    notes: Optional[str] = Field(None, description="Missing data, assumptions, or uncertainties")


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are a Mortgage Offer Comparison Assistant that analyzes mortgage/loan offer documents and compares them to current market conditions.

Your workflow:
1. Extract the PDF text using the extract_pdf_text tool
2. Search for current market mortgage rates in the specified region using web_search
3. Analyze and compare the offer to market conditions

Extract these fields from documents:
- loan_amount: Total principal amount borrowed
- interest_rate_type: fixed, variable, or mixed
- interest_rate_percent: Current nominal rate (as %)
- comparison_rate_or_APR_percent: APR / TAEG / comparison rate (as %)
- loan_term_years: Length of the mortgage
- monthly_payment_amount: Current required payment
- currency: e.g., USD, EUR, GBP
- property_value: If available, for LTV calculation

Compute LTV when possible: LTV = loan_amount / property_value

Categorize rate advantage:
- "better_than_market": offer APR is ≥ 0.25% lower than market
- "similar_to_market": within ±0.25%
- "worse_than_market": ≥ 0.25% higher
- "unknown": insufficient data

Do NOT provide legal, tax, or investment advice. Keep language simple and neutral.
Today's date is: """ + date.today().isoformat()


# ============================================================================
# Agent Tools
# ============================================================================

@tool
def extract_pdf_text(file_path: str) -> str:
    """Extract text content from a PDF mortgage document.
    
    Args:
        file_path: Path to the PDF file to extract text from.
        
    Returns:
        The extracted text content from all pages of the PDF.
    """
    try:
        doc = pymupdf.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"


@tool
def web_search(query: str) -> str:
    """Search the web for current mortgage market information.
    
    Args:
        query: The search query to find mortgage rate information.
        
    Returns:
        A formatted string with search results including titles, snippets, and links.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        cse_id = os.getenv("GOOGLE_CSE_ID")
        
        if not api_key or not cse_id:
            return "Error: GOOGLE_API_KEY or GOOGLE_CSE_ID not configured"
        
        service = build("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(q=query, cx=cse_id, num=5).execute()
        
        if "items" not in result:
            return "No search results found."
        
        formatted_results = []
        for item in result["items"]:
            title = item.get("title", "No title")
            snippet = item.get("snippet", "No description")
            link = item.get("link", "")
            formatted_results.append(f"**{title}**\n{snippet}\nSource: {link}")
        
        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
        return f"Error performing web search: {str(e)}"


# ============================================================================
# Agent Creation
# ============================================================================

def create_mortgage_agent():
    """Create and return the mortgage comparison agent with structured output."""
    
    # Initialize the LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
    )
    
    # Create the ReAct agent with tools and structured output
    tools = [extract_pdf_text, web_search]
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        response_format=MortgageAnalysisResult,
    )
    
    return agent


# ============================================================================
# Result Persistence
# ============================================================================

def persist_analysis(
    pdf_url: str,
    trace_id: str,
    analysis_json: dict,
    messages: list,
) -> Path:
    """
    Persist the analysis result to the filesystem.
    
    Saves the analysis in a JSON file for later retrieval by export_traces.py.
    
    Args:
        pdf_url: The original PDF URL or path.
        trace_id: Langfuse trace ID.
        analysis_json: The structured analysis as a dict.
        messages: Conversation messages from the agent.
        
    Returns:
        Path to the persisted file.
    """
    data = {
        "pdf_url": pdf_url,
        "trace_id": trace_id,
        "analysis_json": analysis_json,
        "messages": messages,
        "timestamp": datetime.now().isoformat(),
    }
    
    with open(LAST_ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return LAST_ANALYSIS_FILE


# ============================================================================
# Main Analysis Function
# ============================================================================

def analyze_mortgage_offer(
    pdf_path: str,
    pdf_url: str = None,
    region: str = None,
    trace_name: str = None,
    persist: bool = True,
) -> dict:
    """
    Analyze a mortgage offer PDF and compare it to current market conditions.
    
    This is the main entry point for running the mortgage analysis agent.
    The agent will:
    1. Extract text from the PDF
    2. Search for current market rates
    3. Compare the offer to market conditions
    4. Return structured analysis
    
    All interactions are logged to Langfuse for observability.
    Results are persisted to disk for later export to Label Studio.
    
    Args:
        pdf_path: Path to the mortgage offer PDF file (local path).
        pdf_url: Original PDF URL (used for persistence, defaults to pdf_path).
        region: Optional region/country for market comparison (e.g., "Portugal", "USA").
        trace_name: Optional name for the Langfuse trace.
        persist: Whether to persist results to disk (default: True).
        
    Returns:
        Dictionary with:
        - "raw": The raw agent result with messages
        - "structured_response": The parsed MortgageAnalysisResult (or None)
        - "analysis_json": The analysis as a plain dict (or None)
        - "trace_id": Langfuse trace ID
        - "messages": Conversation messages for export
        - "pdf_url": The original PDF URL/path
    """
    # Use pdf_path as url if not provided
    pdf_url = pdf_url or pdf_path
    
    # Initialize Langfuse callback handler
    langfuse_handler = CallbackHandler()
    if trace_name:
        langfuse_handler.trace_name = trace_name
    
    # Create the agent
    agent = create_mortgage_agent()
    
    # Build the user message
    user_message = f"Please analyze the mortgage offer in this PDF file: {pdf_path}"
    if region:
        user_message += f"\n\nThe property/mortgage is located in: {region}. Please search for current mortgage rates in this region."
    else:
        user_message += "\n\nPlease try to determine the region from the document and search for current mortgage rates in that region."
    
    # Invoke the agent
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config={"callbacks": [langfuse_handler]},
    )
    
    # Get trace_id from Langfuse handler
    trace_id = getattr(langfuse_handler, "last_trace_id", None)
    
    # Extract and format messages for export
    messages_export = []
    raw_messages = result.get("messages", [])
    for msg in raw_messages:
        msg_dict = {
            "role": getattr(msg, "type", "unknown"),
            "content": getattr(msg, "content", ""),
        }
        # Include tool calls if present
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            msg_dict["tool_calls"] = [
                {"name": tc.get("name"), "args": tc.get("args")}
                for tc in msg.tool_calls
            ]
        # Include tool name for tool messages
        if hasattr(msg, "name") and msg.name:
            msg_dict["tool_name"] = msg.name
        messages_export.append(msg_dict)
    
    # Extract structured response if available
    structured_response = result.get("structured_response")
    analysis_json = None
    
    if structured_response and isinstance(structured_response, MortgageAnalysisResult):
        analysis_json = structured_response.model_dump()
    
    # Persist results to disk for later export
    if persist and analysis_json:
        persist_analysis(
            pdf_url=pdf_url,
            trace_id=trace_id,
            analysis_json=analysis_json,
            messages=messages_export,
        )
    
    return {
        "raw": result,
        "structured_response": structured_response,
        "analysis_json": analysis_json,
        "trace_id": trace_id,
        "messages": messages_export,
        "pdf_url": pdf_url,
    }


# ============================================================================
# CLI Helper Functions
# ============================================================================

def is_url(path: str) -> bool:
    """Check if the given path is a URL."""
    parsed = urllib.parse.urlparse(path)
    return parsed.scheme in ("http", "https")


def download_pdf(url: str, temp_dir: str) -> str:
    """
    Download a PDF from a URL to a temporary directory.
    
    Args:
        url: The URL to download from.
        temp_dir: The temporary directory to save the file.
        
    Returns:
        The path to the downloaded file.
    """
    # Extract filename from URL or generate one
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
    if not filename.lower().endswith(".pdf"):
        filename = "downloaded_mortgage.pdf"
    
    filepath = os.path.join(temp_dir, filename)
    
    print(f"Downloading PDF from URL...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    
    with open(filepath, "wb") as f:
        f.write(response.content)
    
    print(f"Downloaded to temporary file: {filepath}")
    return filepath


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze a mortgage offer PDF and compare it to current market conditions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_agent.py test_data/loan_simulations/example.pdf
    python run_agent.py test_data/loan_simulations/example.pdf --region Portugal
    python run_agent.py https://example.com/mortgage.pdf --region Portugal
        """,
    )
    
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the mortgage offer PDF file or URL to analyze.",
    )
    
    parser.add_argument(
        "--region", "-r",
        type=str,
        default=None,
        help="Region/country for market comparison (e.g., 'Portugal', 'USA', 'Germany').",
    )
    
    parser.add_argument(
        "--trace-name", "-t",
        type=str,
        default=None,
        help="Optional name for the Langfuse trace.",
    )
    
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Disable automatic file export (analysis.json and predictions.json).",
    )
    
    args = parser.parse_args()
    
    # Store original PDF source (URL or path)
    original_pdf_source = args.pdf_path
    temp_dir = None
    local_pdf_path = None
    
    try:
        # Handle URL vs local file
        if is_url(args.pdf_path):
            # Create temp directory and download PDF
            temp_dir = tempfile.mkdtemp(prefix="mortgage_agent_")
            local_pdf_path = download_pdf(args.pdf_path, temp_dir)
        else:
            # Local file
            local_pdf_path = args.pdf_path
            pdf_path = Path(local_pdf_path)
            if not pdf_path.exists():
                print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
                sys.exit(1)
            
            if not pdf_path.suffix.lower() == ".pdf":
                print(f"Warning: File does not have .pdf extension: {pdf_path}", file=sys.stderr)
        
        # Run the analysis
        print(f"Analyzing mortgage offer: {original_pdf_source}")
        if args.region:
            print(f"Region: {args.region}")
        print("-" * 60)
        print("Processing... (this may take a moment)")
        print()
        
        result = analyze_mortgage_offer(
            pdf_path=local_pdf_path,
            pdf_url=original_pdf_source,
            region=args.region,
            trace_name=args.trace_name or "mortgage-analysis",
            persist=True,
        )
        
        # Check for structured output
        analysis_json = result.get("analysis_json")
        trace_id = result.get("trace_id")
        
        if analysis_json:
            # Display structured JSON output
            print("=" * 60)
            print("ANALYSIS JSON:")
            print("=" * 60)
            print(json.dumps(analysis_json, indent=2))
            print()
            
            # Export analysis JSON file (default behavior unless --no-export)
            if not args.no_export:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Export analysis JSON
                analysis_path = Path(f"analysis_{timestamp}.json")
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump(analysis_json, f, indent=2, ensure_ascii=False)
                print(f"Analysis JSON saved to: {analysis_path}")
            
            print()
            print("=" * 60)
            print(f"Trace logged to Langfuse (ID: {trace_id})")
            print(f"Analysis persisted to: {LAST_ANALYSIS_FILE}")
            print("Use 'python export_traces.py --export-last' to export to Label Studio.")
        else:
            # Fallback to raw message content
            raw = result.get("raw", {})
            if "messages" in raw and raw["messages"]:
                final_message = raw["messages"][-1]
                print("=" * 60)
                print("ANALYSIS RESULT (raw):")
                print("=" * 60)
                print()
                print(final_message.content)
                print()
                print("=" * 60)
                print("Note: Structured output parsing failed. Raw response shown above.")
            else:
                print("No response received from the agent.")
                sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nAnalysis cancelled by user.")
        sys.exit(130)
    except requests.RequestException as e:
        print(f"Error downloading PDF: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        raise
    finally:
        # Clean up temp directory if created
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up temporary files.")


if __name__ == "__main__":
    main()
