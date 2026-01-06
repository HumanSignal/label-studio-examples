#!/usr/bin/env python3
"""
FastAPI Server for Mortgage Offer Comparison Agent

Provides a web interface for analyzing mortgage PDFs with real-time feedback.

Workflow:
---------
1. User provides a URL to a PDF mortgage document
2. Server downloads and analyzes the PDF, streaming status updates
3. Upon completion, user can:
   - View the analysis results
   - Open the trace in Langfuse for detailed observability
   - Export to Label Studio for annotation and redirect there

Endpoints:
----------
- GET /           : Serves the HTML frontend
- POST /analyze   : Analyzes a PDF (accepts URL), returns results
- POST /export    : Exports the trace to Label Studio

Usage:
------
    python server.py
    # Then open http://localhost:8000 in your browser

Environment Variables:
----------------------
- All variables from run_agent.py (OPENAI_API_KEY, GOOGLE_*, LANGFUSE_*)
- LANGFUSE_PROJECT_ID: Langfuse project ID for trace URL (default: cmk2dufsk048mad06ysgepvnt)
- LABEL_STUDIO_URL, LABEL_STUDIO_API_KEY, LABEL_STUDIO_PROJECT_ID
"""

import os
import shutil
import tempfile
from datetime import datetime
from typing import Optional

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from export_traces import export_last_analysis_to_label_studio
from run_agent import analyze_mortgage_offer, download_pdf

# Load environment variables
load_dotenv()

# Constants
LANGFUSE_PROJECT_ID = os.getenv("LANGFUSE_PROJECT_ID")
LANGFUSE_TRACES_URL = f"https://cloud.langfuse.com/project/{LANGFUSE_PROJECT_ID}/traces"
LABEL_STUDIO_PROJECT_ID = os.getenv("LABEL_STUDIO_PROJECT_ID", "1")
LABEL_STUDIO_BASE_URL = os.getenv("LABEL_STUDIO_URL", "http://localhost:8001")


# ============================================================================
# Pydantic Models
# ============================================================================

class AnalyzeRequest(BaseModel):
    pdf_url: str
    region: Optional[str] = None


class AnalyzeResponse(BaseModel):
    success: bool
    trace_id: Optional[str] = None
    pdf_url: Optional[str] = None
    analysis: Optional[dict] = None
    error: Optional[str] = None


class ExportResponse(BaseModel):
    success: bool
    label_studio_url: str
    error: Optional[str] = None


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Mortgage Offer Comparison Agent",
    description="Analyze mortgage PDFs and compare to market conditions",
)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the HTML frontend."""
    return HTML_FRONTEND


@app.get("/config")
async def get_config():
    """Return frontend configuration including external URLs."""
    return {
        "langfuse_traces_url": LANGFUSE_TRACES_URL,
        "label_studio_base_url": LABEL_STUDIO_BASE_URL,
        "label_studio_project_id": LABEL_STUDIO_PROJECT_ID,
    }


@app.post("/analyze")
async def analyze_pdf(request: AnalyzeRequest):
    """
    Analyze a mortgage PDF from URL.
    
    Downloads the PDF, runs the analysis agent (which persists results),
    and returns results.
    """
    temp_dir = None
    try:
        # Create temp directory and download PDF
        temp_dir = tempfile.mkdtemp(prefix="mortgage_agent_")
        local_pdf_path = download_pdf(request.pdf_url, temp_dir)
        
        # Run the analysis (persistence is handled by analyze_mortgage_offer)
        result = analyze_mortgage_offer(
            pdf_path=local_pdf_path,
            pdf_url=request.pdf_url,
            region=request.region,
            trace_name=f"web-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            persist=True,
        )
        
        return AnalyzeResponse(
            success=True,
            trace_id=result.get("trace_id"),
            pdf_url=request.pdf_url,
            analysis=result.get("analysis_json"),
        )
        
    except requests.RequestException as e:
        return AnalyzeResponse(
            success=False,
            error=f"Failed to download PDF: {str(e)}",
        )
    except Exception as e:
        return AnalyzeResponse(
            success=False,
            error=f"Analysis failed: {str(e)}",
        )
    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@app.post("/export")
async def export_to_label_studio():
    """
    Export the last analysis to Label Studio.
    
    Uses the export_last_analysis_to_label_studio function from export_traces.py
    which handles loading the persisted analysis, converting to predictions format,
    and uploading to Label Studio.
    
    Returns the URL to the Label Studio project for annotation.
    """
    try:
        result = export_last_analysis_to_label_studio(project_id=LABEL_STUDIO_PROJECT_ID)
        
        if result["success"]:
            return ExportResponse(
                success=True,
                label_studio_url=result["label_studio_url"],
            )
        else:
            return ExportResponse(
                success=False,
                label_studio_url="",
                error=result.get("error", "Export failed"),
            )
        
    except Exception as e:
        return ExportResponse(
            success=False,
            label_studio_url="",
            error=f"Export failed: {str(e)}",
        )


# ============================================================================
# HTML Frontend
# ============================================================================

HTML_FRONTEND = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mortgage Offer Analyzer</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-tertiary: #1a2234;
            --accent-cyan: #22d3ee;
            --accent-purple: #a78bfa;
            --accent-emerald: #34d399;
            --accent-amber: #fbbf24;
            --accent-rose: #fb7185;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border-color: #2d3a52;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Space Grotesk', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 20% 0%, rgba(34, 211, 238, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(167, 139, 250, 0.08) 0%, transparent 50%);
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }
        
        header {
            text-align: center;
            margin-bottom: 3rem;
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }
        
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 1.5rem;
        }
        
        .input-group {
            margin-bottom: 1.5rem;
        }
        
        label {
            display: block;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        input[type="text"], input[type="url"] {
            width: 100%;
            padding: 1rem 1.25rem;
            font-size: 1rem;
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-tertiary);
            border: 2px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-primary);
            transition: all 0.2s ease;
        }
        
        input:focus {
            outline: none;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.15);
        }
        
        input::placeholder {
            color: var(--text-muted);
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            font-family: 'Space Grotesk', sans-serif;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-cyan), #06b6d4);
            color: var(--bg-primary);
        }
        
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(34, 211, 238, 0.35);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            border: 2px solid var(--border-color);
            color: var(--text-primary);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent-purple);
            background: rgba(167, 139, 250, 0.1);
        }
        
        .btn-success {
            background: linear-gradient(135deg, var(--accent-emerald), #10b981);
            color: var(--bg-primary);
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(52, 211, 153, 0.35);
        }
        
        .status-panel {
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 1.5rem;
            margin-top: 1.5rem;
            display: none;
        }
        
        .status-panel.visible {
            display: block;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .status-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .status-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .status-icon.loading {
            background: rgba(251, 191, 36, 0.2);
            color: var(--accent-amber);
        }
        
        .status-icon.success {
            background: rgba(52, 211, 153, 0.2);
            color: var(--accent-emerald);
        }
        
        .status-icon.error {
            background: rgba(251, 113, 133, 0.2);
            color: var(--accent-rose);
        }
        
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid transparent;
            border-top-color: currentColor;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .status-text {
            font-weight: 500;
        }
        
        .status-messages {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-secondary);
            max-height: 150px;
            overflow-y: auto;
        }
        
        .status-messages p {
            padding: 0.25rem 0;
            border-bottom: 1px solid var(--border-color);
        }
        
        .status-messages p:last-child {
            border-bottom: none;
        }
        
        .results-panel {
            display: none;
        }
        
        .results-panel.visible {
            display: block;
            animation: fadeIn 0.3s ease;
        }
        
        .results-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
        }
        
        .results-header h2 {
            font-size: 1.3rem;
            color: var(--accent-emerald);
        }
        
        .action-buttons {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .result-item {
            background: var(--bg-tertiary);
            border-radius: 10px;
            padding: 1rem;
        }
        
        .result-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.25rem;
        }
        
        .result-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .result-value.highlight-good {
            color: var(--accent-emerald);
        }
        
        .result-value.highlight-bad {
            color: var(--accent-rose);
        }
        
        .result-value.highlight-neutral {
            color: var(--accent-amber);
        }
        
        .recommendation-box {
            background: linear-gradient(135deg, rgba(167, 139, 250, 0.1), rgba(34, 211, 238, 0.1));
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.25rem;
            margin-top: 1rem;
        }
        
        .recommendation-box h3 {
            font-size: 0.9rem;
            color: var(--accent-purple);
            margin-bottom: 0.5rem;
        }
        
        .recommendation-box p {
            color: var(--text-secondary);
            line-height: 1.6;
        }
        
        .icon {
            width: 18px;
            height: 18px;
        }
        
        /* Toast notifications */
        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1rem 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1000;
        }
        
        .toast.visible {
            transform: translateY(0);
            opacity: 1;
        }
        
        .toast.success {
            border-color: var(--accent-emerald);
        }
        
        .toast.error {
            border-color: var(--accent-rose);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📄 Mortgage Analyzer</h1>
            <p class="subtitle">AI-powered mortgage offer comparison against market conditions</p>
        </header>
        
        <div class="card">
            <form id="analyzeForm">
                <div class="input-group">
                    <label for="pdfUrl">PDF Document URL</label>
                    <input 
                        type="url" 
                        id="pdfUrl" 
                        name="pdfUrl" 
                        placeholder="https://example.com/mortgage-offer.pdf"
                        required
                    >
                </div>
                
                <div class="input-group">
                    <label for="region">Region (Optional)</label>
                    <input 
                        type="text" 
                        id="region" 
                        name="region" 
                        placeholder="e.g., Portugal, Germany, USA"
                    >
                </div>
                
                <button type="submit" class="btn btn-primary" id="analyzeBtn">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                    </svg>
                    Analyze Mortgage Offer
                </button>
            </form>
            
            <div class="status-panel" id="statusPanel">
                <div class="status-header">
                    <div class="status-icon loading" id="statusIcon">
                        <div class="spinner"></div>
                    </div>
                    <span class="status-text" id="statusText">Processing...</span>
                </div>
                <div class="status-messages" id="statusMessages"></div>
            </div>
        </div>
        
        <div class="card results-panel" id="resultsPanel">
            <div class="results-header">
                <h2>✓ Analysis Complete</h2>
                <div class="action-buttons">
                    <a href="#" 
                       target="_blank" 
                       class="btn btn-secondary"
                       id="langfuseLink">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                            <path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                        </svg>
                        Open Langfuse
                    </a>
                    <button class="btn btn-success" id="exportBtn">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                        </svg>
                        Annotate in Label Studio
                    </button>
                </div>
            </div>
            
            <div class="results-grid" id="resultsGrid"></div>
            
            <div class="recommendation-box" id="recommendationBox">
                <h3>Recommendation</h3>
                <p id="recommendationText"></p>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast">
        <span id="toastMessage"></span>
    </div>

    <script>
        const form = document.getElementById('analyzeForm');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const statusPanel = document.getElementById('statusPanel');
        const statusIcon = document.getElementById('statusIcon');
        const statusText = document.getElementById('statusText');
        const statusMessages = document.getElementById('statusMessages');
        const resultsPanel = document.getElementById('resultsPanel');
        const resultsGrid = document.getElementById('resultsGrid');
        const recommendationText = document.getElementById('recommendationText');
        const exportBtn = document.getElementById('exportBtn');
        const langfuseLink = document.getElementById('langfuseLink');
        
        let currentAnalysis = null;
        let appConfig = {};
        
        // Fetch configuration on page load
        (async function loadConfig() {
            try {
                const response = await fetch('/config');
                appConfig = await response.json();
                langfuseLink.href = appConfig.langfuse_traces_url;
            } catch (e) {
                console.error('Failed to load config:', e);
            }
        })();
        
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            const toastMessage = document.getElementById('toastMessage');
            toast.className = 'toast ' + type;
            toastMessage.textContent = message;
            toast.classList.add('visible');
            setTimeout(() => toast.classList.remove('visible'), 4000);
        }
        
        function addStatusMessage(msg) {
            const p = document.createElement('p');
            p.textContent = `→ ${msg}`;
            statusMessages.appendChild(p);
            statusMessages.scrollTop = statusMessages.scrollHeight;
        }
        
        function setStatus(state, text) {
            statusText.textContent = text;
            statusIcon.className = 'status-icon ' + state;
            
            if (state === 'loading') {
                statusIcon.innerHTML = '<div class="spinner"></div>';
            } else if (state === 'success') {
                statusIcon.innerHTML = '✓';
            } else if (state === 'error') {
                statusIcon.innerHTML = '✕';
            }
        }
        
        function getMarketPositionClass(position) {
            if (position === 'better_than_market') return 'highlight-good';
            if (position === 'worse_than_market') return 'highlight-bad';
            return 'highlight-neutral';
        }
        
        function formatMarketPosition(position) {
            const labels = {
                'better_than_market': 'Better than Market',
                'similar_to_market': 'Similar to Market',
                'worse_than_market': 'Worse than Market',
                'unknown': 'Unknown'
            };
            return labels[position] || position;
        }
        
        function formatCurrency(amount, currency) {
            if (!amount) return 'N/A';
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: currency || 'EUR',
                maximumFractionDigits: 0
            }).format(amount);
        }
        
        function renderResults(analysis) {
            currentAnalysis = analysis;
            const ls = analysis.loan_summary || {};
            const ms = analysis.market_snapshot || {};
            const cr = analysis.comparison_result || {};
            
            resultsGrid.innerHTML = `
                <div class="result-item">
                    <div class="result-label">Loan Amount</div>
                    <div class="result-value">${formatCurrency(ls.loan_amount, ls.currency)}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Interest Rate</div>
                    <div class="result-value">${ls.interest_rate_percent ? ls.interest_rate_percent + '%' : 'N/A'}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">APR / TAEG</div>
                    <div class="result-value">${ls.comparison_rate_or_APR_percent ? ls.comparison_rate_or_APR_percent + '%' : 'N/A'}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Loan Term</div>
                    <div class="result-value">${ls.loan_term_years ? ls.loan_term_years + ' years' : 'N/A'}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Monthly Payment</div>
                    <div class="result-value">${formatCurrency(ls.monthly_payment_amount, ls.currency)}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Rate Type</div>
                    <div class="result-value">${ls.interest_rate_type ? ls.interest_rate_type.charAt(0).toUpperCase() + ls.interest_rate_type.slice(1) : 'N/A'}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Region</div>
                    <div class="result-value">${ms.region || 'N/A'}</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Market Position</div>
                    <div class="result-value ${getMarketPositionClass(cr.rate_position_vs_market)}">${formatMarketPosition(cr.rate_position_vs_market)}</div>
                </div>
            `;
            
            recommendationText.textContent = analysis.recommendation || 'No specific recommendation available.';
            
            if (analysis.notes) {
                recommendationText.textContent += ' Note: ' + analysis.notes;
            }
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const pdfUrl = document.getElementById('pdfUrl').value.trim();
            const region = document.getElementById('region').value.trim();
            
            if (!pdfUrl) return;
            
            // Reset and show status
            statusMessages.innerHTML = '';
            resultsPanel.classList.remove('visible');
            statusPanel.classList.add('visible');
            setStatus('loading', 'Starting analysis...');
            analyzeBtn.disabled = true;
            
            addStatusMessage('Downloading PDF document...');
            
            try {
                // Simulate progress messages
                setTimeout(() => addStatusMessage('Extracting text from PDF...'), 1000);
                setTimeout(() => addStatusMessage('Searching for current market rates...'), 2500);
                setTimeout(() => addStatusMessage('Comparing offer to market conditions...'), 4000);
                
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pdf_url: pdfUrl,
                        region: region || null
                    })
                });
                
                const data = await response.json();
                
                if (data.success && data.analysis) {
                    setStatus('success', 'Analysis complete!');
                    addStatusMessage('Analysis completed successfully');
                    
                    renderResults(data.analysis);
                    resultsPanel.classList.add('visible');
                    
                    showToast('Mortgage analysis completed successfully!', 'success');
                } else {
                    setStatus('error', 'Analysis failed');
                    addStatusMessage('Error: ' + (data.error || 'Unknown error'));
                    showToast(data.error || 'Analysis failed', 'error');
                }
            } catch (error) {
                setStatus('error', 'Request failed');
                addStatusMessage('Error: ' + error.message);
                showToast('Failed to connect to server', 'error');
            } finally {
                analyzeBtn.disabled = false;
            }
        });
        
        exportBtn.addEventListener('click', async () => {
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<div class="spinner"></div> Exporting...';
            
            try {
                const response = await fetch('/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showToast('Exported to Label Studio!', 'success');
                    // Redirect to Label Studio
                    window.open(data.label_studio_url, '_blank');
                } else {
                    showToast(data.error || 'Export failed', 'error');
                }
            } catch (error) {
                showToast('Failed to export: ' + error.message, 'error');
            } finally {
                exportBtn.disabled = false;
                exportBtn.innerHTML = `
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                    </svg>
                    Annotate in Label Studio
                `;
            }
        });
    </script>
</body>
</html>
"""


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    print("Starting Mortgage Offer Comparison Agent Server...")
    print("Open http://localhost:8888 in your browser")
    print("-" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8888)

