"""
Simple demonstration of FastMCP with BigQuery integration.
This is a tutorial example - not for production use.
"""

import os
from typing import Optional
from mcp.server.fastmcp import FastMCP
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from dotenv import load_dotenv

# Initialize FastMCP app
app = FastMCP("data_processing_agent_tutorial")

# Load environment variables
load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")
LABEL_COLUMN_NAME = "__label"

# Simple in-memory storage
memory = {}

# BigQuery Tools
@app.tool()
async def connect_to_bigquery() -> str:
    """Connect to BigQuery using service account credentials"""
    try:
        credentials = service_account.Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        
        # Test connection
        next(client.list_datasets())
        
        # Store client in memory
        memory['bq_client'] = client
        return f"Connected to BigQuery project: {PROJECT_ID}"
    except Exception as e:
        return f"Failed to connect: {str(e)}"

@app.tool()
async def preview_table(dataset_id: str, table_id: str, limit: int = 5) -> str:
    """Preview rows from a BigQuery table"""
    client = memory.get('bq_client')
    if not client:
        return "Not connected to BigQuery. Use connect_to_bigquery first."
    
    query = f"""
    SELECT *
    FROM `{dataset_id}.{table_id}`
    LIMIT {limit}
    """
    
    try:
        df = client.query(query).to_dataframe()
        return f"Preview of {dataset_id}.{table_id}:\n{df.to_string()}"
    except Exception as e:
        return f"Error previewing table: {str(e)}"

@app.tool()
async def run_query(query: str, save_as: Optional[str] = None) -> str:
    """Run a BigQuery SQL query and optionally save results"""
    client = memory.get('bq_client')
    if not client:
        return "Not connected to BigQuery. Use connect_to_bigquery first."
    
    try:
        df = client.query(query).to_dataframe()
        result = f"Query returned {len(df)} rows"
        
        if save_as:
            memory[save_as] = df
            return f"{result}\nResults saved as '{save_as}'"
        
        return f"{result}\n{df.head().to_string()}"
    except Exception as e:
        return f"Query failed: {str(e)}"
    
@app.tool()
async def export_to_csv(variable_name: str, file_path: str) -> str:
    """Export a variable to a CSV file."""
    df = memory.get(variable_name)
    if df is None:
        return f"No variable named '{variable_name}' found"
    # Create output directory if it doesn't exist
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure file path is within output directory
    output_path = output_dir / file_path
    
    # Save dataframe to CSV, appending if file exists
    if output_path.exists():
        existing_df = pd.read_csv(output_path)
        df = pd.concat([existing_df, df], ignore_index=True)
    df[LABEL_COLUMN_NAME] = variable_name
    df.to_csv(output_path, index=False)
    return f"Data exported successfully to {output_path}"
