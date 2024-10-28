# OpenAI Fine-Tuning Example

This directory contains an example of fine-tuning an OpenAI model using a custom dataset about hurricanes. The process is demonstrated in a Jupyter notebook.

## Contents

- `OpenAI_fine-tuning.ipynb`: Jupyter notebook containing the complete fine-tuning process.
- `qa_pairs_openai_wiki_hurricane.json`: JSON file containing the question-answer pairs generated with OpenAI from Wikipedia revisions about hurricanes.

## Overview

The notebook covers the following steps:

1. Data Curation and Preparation
   - Collecting data from Wikipedia revisions about hurricanes
   - Generating question-answer pairs from the collected data

2. Dataset Analysis and Formatting
   - Analyzing the dataset for token counts and distribution
   - Formatting the data for OpenAI's fine-tuning requirements

3. Fine-Tuning Process
   - Uploading the dataset to OpenAI
   - Creating and monitoring a fine-tuning job

4. Using the Fine-Tuned Model
   - Demonstrating how to use the fine-tuned model for hurricane-related queries

## Requirements

To run this notebook, you'll need:

- Python 3.x
- Jupyter Notebook
- OpenAI Python library
- Other dependencies listed in `requirements.txt`

## Usage

1. Install the required dependencies:   ```
   pip install -r requirements.txt   ```

2. Open the `OpenAI_fine-tuning.ipynb` notebook in Jupyter.

3. Follow the steps in the notebook, ensuring you have the necessary OpenAI API credentials.

## Note

This example uses a specific dataset about hurricanes. You may need to adjust the data collection and preparation steps for your own use case.
