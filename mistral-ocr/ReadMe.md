# Using Label Studio to Evaluate MistralOCR 
[Label Studio](labelstud.io) allows you to evaluate and correct mistral output.

![Labeling_Screen.png](Labeling_Screen.png)

In this project, we'll help you set up a new Label Studio project, 
upload a multi-page pdf (converted to images), and then we'll use 
the Mistral API to run OCR over that document and upload the results to 
Label Studio for easy evaluation. 

## Prerequisites 
You'll need to have the following to run this repo: 
1. Label Studio running, with an account that you can get the token for. 
  To install Label Studio, simply run:
  ```
  pip install label-studio
  ```

2. A MistralAI account and API key. To create an account, click [here](console.mistral.ai).
Then, go to the API keys page and create a new key by clicking "Create new key". Make
sure to copy this, as it won't be available after you close the window! 
3. Jupyter notebook installed on your machine. 

## Getting Started 
1. Copy this repo to your local machine 
2. Open `MistralOCR-LabelStudio-example.ipynb` in Jupyter Notebook (or your favorite notebook running system)
3. Run the first cell to install all necessary packages. 
4. In the second cell, fill in your API keys and URLs
5. Run the following cells in order to create your project in your Label Studio instance, 
upload a sample task, run MistralOCR over that sample task, and upload the results to Label Studio.

## What now? 
To evaluate MistralOCR, we reccomend comparing the text of the document with the text provided by the model. 
That field is editable, so you can make any and all necessary changes. You can then pull the data from Label Studio and 
run metrics to get a sense of how often the documents you use need to be edited. 

You can also add other types of control tags to this project. For instance, a rating field could be useful to get 
an overall judgement of how well the model performed. 
