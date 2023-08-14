import label_studio_sdk as ls
from langchain.callbacks.base import BaseCallbackHandler

import json
import re

class LabelStudioCallbackHandler(BaseCallbackHandler):
  def __init__(self, api_key, url, project_id):
    self.ls_client = ls.Client(url=url, api_key=api_key)
    self.ls_project = self.ls_client.get_project(project_id)
    self.prompts = {}

  def on_llm_start(self, serialized, prompts, **kwargs):
    self.prompts[str(kwargs["parent_run_id"] or kwargs["run_id"])] = prompts

  def on_llm_end(self, response, **kwargs):
    run_id = str(kwargs["parent_run_id"] or kwargs["run_id"])
    prompts = self.prompts[run_id]

    tasks = []
    for prompt, generation in zip(prompts, response.generations):
      match = re.search(r'Human: (\[.*?\])', prompt)
      if match:
          json_string = match.group(1)
          data = json.loads(json_string.replace('\'', '\"'))  # replace single quotes with double quotes for valid JSON
          print(data)
          
          # Extract the 'content' field from the first dictionary in the list
          content = data[0]["content"]
          
      tasks.append({'prompt': content, 'response': generation[0].text})
    self.ls_project.import_tasks(tasks)

    self.prompts.pop(run_id)