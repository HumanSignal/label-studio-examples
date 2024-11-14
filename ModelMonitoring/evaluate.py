import json
from pathlib import Path

exported_data_path = Path( ".", 'ls_data.json')

with exported_data_path.open(mode='r') as f:
    data_json = json.load(f)

origins = [task["annotations"][0]["result"][0]["origin"] for task in data_json]
count_changed = origins.count("prediction-changed")
pct_changed = (count_changed/len(origins))*100

print(f"You changed {count_changed} of the original predictions. This means you had to edit "
      f"your model's output {pct_changed}% of the time.")

if pct_changed < 75:
    print(f"Your model passed this week!")
else:
    print(f"You may want to consider retraining or changing your model")

