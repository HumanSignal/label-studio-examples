# Data Processing Agent Example

This tutorial showing how an AI agent might interface with [Google BigQuery]() through the [MCP (Multi-Context Platform) Claude interface](), to address a simple data discovery and annotation task. This tutorial is not production-ready but illustrates the main components involved. [Read more in our blog post]()

## Installation

1. Clone this repo and use [uv]() to manage your Python projects:

```
cd data-processing-agent/
uv init .
uv add mcp[cli] google-cloud-bigquery pandas db-dtypes python-doten
```

2. Provide path to your [Google Application Credentials]() json file and specify your Google Project ID in `.env` file.

3. Download [Claude Desktop app]() and install tools for Claude:

    ```
    uv run mcp install --env-file .env --with-editable . bq_tutorial.py
    ```
    Read more about [Model Context Protocol for Claude]()


## Usage

Launch Claude and interact with your table, using `dataset_id` and `table_id` from your BiqQuery console. You should be able to see results of execution as CSV files with labeled data in the output directory `.output`.

For example:
```txt
Given my sales rep data lives in BigQuery table `september_outreach` under the dataset `sales_rep`, analyze the columns related to the customer use case and sales rep notes. Extract representative examples where customers express objections related to pricing, feature gaps, or competitor comparisons. 
```
