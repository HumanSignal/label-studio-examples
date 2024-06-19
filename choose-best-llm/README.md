# Choosing the Best Open Source LLM for Your Application

Code for the workshop "Choosing the Best Open Source LLM for Your Application" at the 2024 AI_dev summit.

* Presentation: https://docs.google.com/presentation/d/1Zf9PJ1isptm-s-4UjgZ8016VbCr65ZTdOPsc1BtxxaE/edit?usp=sharing

* Explore demo instance: [https://ls-workshop.dev.heartex.com/](https://ls-workshop.dev.heartex.com/user/signup/?token=6QxZ0zBQiXbU8bMLu0I26wvtM8YgQZ5RIUlzqvP9)


or follow along the steps bellow to install your own instance:


## Create the evaluation UI with Label Studio

1. Install [Label Studio](https://labelstud.io/):

```bash
pip install label-studio
```

2. Create a new Label Studio project by clicking on `Create` -> `Save`.

3. Import tasks from [tasks.json](tasks.json) file. It contains hundreds of transcribed invoices, where each task represents a single invoice:
```json
{
  "doc": "invoice_1.jpg",
  "text": "transcribed text of the invoice",
  "lang": "en"
}
```

4. Now configure your labeling UI in project `Settings > Labeling Interface > Code` with [structured_output_config.xml](structured_output_config.xml). It contains the following components:


**Classification task:**
```xml
<Choices name="invoice_category" toName="doc" layout="select"
         prompt="Provide the invoice category.">
    <Choice value="Groceries"/>
    <Choice value="Cafés/Coffeeshops"/>
    <Choice value="Dining/Restaurants"/>
    <Choice value="Clothing/Apparel"/>
    <Choice value="Electronics"/>
    <Choice value="Home Improvement"/>
    <Choice value="Health/Pharmacy"/>
    <Choice value="Gasoline/Fuel"/>
    <Choice value="Transportation/Travel"/>
    <Choice value="Entertainment/Leisure"/>
    <Choice value="Utilities/Bills"/>
    <Choice value="Insurance"/>
    <Choice value="Gifts/Donations"/>
    <Choice value="Personal Care"/>
    <Choice value="Education/Books"/>
    <Choice value="Professional Services"/>
    <Choice value="Membership/Subscriptions"/>
    <Choice value="Taxes"/>
    <Choice value="Vehicle Maintenance/Repairs"/>
    <Choice value="Pet Care"/>
    <Choice value="Home Furnishings/Decor"/>
    <Choice value="Other"/>
</Choices>
```

**Datetime extraction task:**
```xml
<DateTime name="invoice_date" toName="doc" only="date"
          prompt="Extract the invoice date."/>
```

**Entity extraction task:**
```xml
<TextArea name="store_name" toName="doc" maxSubmissions="1" editable="true" showSubmitButton="false"
          prompt="Extract the store name."/>
```

**Number extraction task:**
```xml
<Number name="total_amount" toName="doc" slider="true"
        prompt="Calculate the total amount paid."/>
```


## Connect LLMs

### Install the Label Studio ML plugin:

It allows model server integration with Label Studio.
```bash
pip install label-studio-ml
```

### Configure the LLM server:

First make sure you have [sglang server](https://github.com/sgl-project/sglang) running. For this demo, you can use the following deployments of the 8 different LLMs:
```json
{
  "codegemma": "https://codegemma-7b-it-inf-workshop.dev.heartex.com",
  "codellama": "https://codellama-7b-hf-inf-workshop.dev.heartex.com",
  "deepseek": "https://deepseek-coder-6-7b-it-inf-workshop.dev.heartex.com",
  "gemma": "https://gemma-7b-it-inf-workshop.dev.heartex.com",
  "meta-llama": "https://meta-llama-3-8b-it-inf-workshop.dev.heartex.com",
  "mistral": "https://mistral-7b-it-inf-workshop.dev.heartex.com",
  "qwen2": "https://qwen2-7b-it-inf-workshop.dev.heartex.com",
  "stablelm": "https://stablelm-2-1-6b-inf-workshop.dev.heartex.com"
}
```
Provide this setup in  [./llms/llms.json](llms/llms.json) file.

### Start the LLM server:
```bash
label-studio-ml start llms
```

or using docker
```bash
docker-compose up
```
   
### Export the LLM server URL:

If you connect to external Label Studio, use [`ngrok`](https://ngrok.com/) to expose the server to the internet:

```bash
ngrok http 9090
```

and grab the URL to connect to the server, e.g. `https://<your-ngrok-id>.ngrok-free.app/`

Check you can access the server by opening the URL in your browser.


### Connect the LLM server to Label Studio:

Go to project `Settings > Model` and **Add Model** with the required URL.

### Start labeling

When you click on `Label All Tasks`, it automatically compares your annotation with LLMs' predictions.

## Display Evaluation Metrics

### Install prerequisites:

```bash
pip install -r dashboard_server/requirements.txt
```

### Run evaluation script

```bash
python dashboard_server/get_stats.py
```

#### Start the dashboard server:

```bash
uvicorn server:app --reload --port 4321
```

Make sure you have the server running and accessible at `http://localhost:4321/`. Expose it to the internet using [`ngrok`](https://ngrok.com/) if needed.

### Connect the dashboard to Label Studio:

Go to project `Settings > Webhooks` and add a new webhook with the URL of the dashboard server, e.g. `http://<your-dashboard-server>.ngrok.io/webhook`.

Now you can see the evaluation metrics in the dashboard. Every time you submit the annotation, the dashboard will update the metrics.
