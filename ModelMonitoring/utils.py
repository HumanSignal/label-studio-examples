import json
import logging
from configparser import ConfigParser

from label_studio_sdk.client import LabelStudio
from label_studio_sdk.label_interface import LabelInterface

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

config = ConfigParser()
config.read('config.ini')

label_studio_url = config["labelstudio"]["LabelStudioURL"]
label_studio_api = config["labelstudio"]["LabelStudioAPI"]
label_studio_project_id = config["labelstudio"]["LabelStudioProjectID"]
labeling_config = config["labelstudio"]["LabelingConfig"]

ls = LabelStudio(base_url=label_studio_url, api_key=label_studio_api)
if labeling_config:
    label_config = labeling_config
elif label_studio_project_id:
    sample_project = ls.projects.get(id=label_studio_project_id)
    label_config = sample_project.label_config
else:
    logger.info("You must provide either the id of the LS project that you'd like to use "
                "the config from or a labeling config")
    raise Exception("Config[\"labelstudio\"] must have either the LabelStudioProjectID or the LablingConfig!")

li = LabelInterface(label_config)

sample_pred = li.generate_sample_prediction()
sample_pred = json.dumps(sample_pred, indent=4)
print(sample_pred)