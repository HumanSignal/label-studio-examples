# Example of using Langfuse and Label Studio

A LangGraph-powered agent that analyzes financial PDF documents (mortgage simulations) and compares them to market conditions, with integrated observability (Langfuse) and expert error analysis (Label Studio).

## The Two-Phase Observability & Evaluation Strategy

![Langfuse and Label Studio Integration](https://hs-sandbox-pub.s3.us-east-1.amazonaws.com/blogs-draft/Langfuse%2BLS.png)


### Why Both?

| Langfuse | Label Studio |
|----------|--------------|
| Automated monitoring | Human expert review |
| Catches known issues | Discovers unknown issues |
| Real-time alerts | Deep-dive analysis |
| Quantitative metrics | Qualitative feedback |
| "Is the system working?" | "Is the output correct?" |

**Langfuse tells you _that_ something went wrong.**  
**Label Studio helps you understand _what_ went wrong and _how to fix it_.**

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Rename .env.example -> .env and set parameters

# Run the web interface
python server.py
# Open http://localhost:8888
```

## The Workflow

### 1. Analyze a Document

Submit a mortgage PDF URL through the web UI or CLI:

```bash
# CLI
python server.py

# Open http://localhost:8888
```

The agent:
- Extracts text from the PDF
- Searches for current market rates
- Compares the offer to market conditions
- Returns structured analysis (loan terms, market snapshot, recommendation)

### 2. Monitor in Langfuse

Every analysis is automatically traced to Langfuse:

- **Trace timeline**: See the full agent execution flow
- **Tool calls**: Which tools were invoked and their outputs
- **Token usage**: Cost tracking per request
- **Latency breakdown**: Where time is spent

Click "Open Langfuse" in the UI to jump directly to the trace.

### 3. Export to Label Studio for Expert Review

Click "Annotate in Label Studio" to:

1. Export the agent's analysis as a pre-annotation
2. Create a task in Label Studio with the PDF and predictions
3. Allow domain experts to:
   - Verify extracted values
   - Correct errors
   - Flag edge cases
   - Build evaluation datasets

## Project Structure

```
pdf-agent/
├── server.py           # FastAPI web interface
├── run_agent.py        # LangGraph Example agent + Langfuse tracing
├── export_traces.py    # Label Studio export utilities
```

## Environment Variables

Put these in a .env file in the root of the project:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 |
| `GOOGLE_API_KEY` | Google API key for Custom Search |
| `GOOGLE_CSE_ID` | Google Custom Search Engine ID |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_PROJECT_ID` | Langfuse project ID (for trace URLs) |
| `LABEL_STUDIO_URL` | Label Studio instance URL |
| `LABEL_STUDIO_API_KEY` | Label Studio API key |
| `LABEL_STUDIO_PROJECT_ID` | Target Label Studio project |

## When to Use This Pattern

This Langfuse + Label Studio integration is valuable when:

- ✅ Your agent produces complex, structured and multi-modal outputs
- ✅ Correctness matters more than just "it didn't crash"
- ✅ Domain expertise is needed to evaluate quality
- ✅ You want to build evaluation datasets over time
- ✅ You need both real-time monitoring AND deep analysis
