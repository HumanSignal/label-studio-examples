import json
import logging
from configparser import ConfigParser

from label_studio_sdk.client import LabelStudio
from label_studio_sdk.label_interface import LabelInterface

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

def start_label_studio(label_studio_url, label_studio_api, label_studio_project_id, labeling_config):
    """
    Start a label studio instance and pull the correct labeling config from the specified project or the config.ini file.
    Args:
        label_studio_url: URL to your Label Studio Instance
        label_studio_api: API key for your Label Studio Instance
        label_studio_project_id: the project ID of the project for which you'd like to use the labeling config
        labeling_config: the string version of the labeling config, if not specifying a project id.

    Returns: the labeling config as a string

    """
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
    return label_config

def get_sample_prediction(label_config):
    """
    Generates a sample prediction (for a PredictionValue object) for the given labeling config.
    Args:
        label_config: the string of the labeling config for which we'd like to generate a prediction.

    Returns: NONE, prints the sample prediction

    """
    li = LabelInterface(label_config)

    sample_pred = li.generate_sample_prediction()
    sample_pred = json.dumps(sample_pred, indent=4)
    print(sample_pred)

if __name__ == "__main__":
    config = ConfigParser()
    config.read('config.ini')

    label_studio_url = config["labelstudio"]["LabelStudioURL"]
    label_studio_api = config["labelstudio"]["LabelStudioAPI"]
    label_studio_project_id = config["labelstudio"]["LabelStudioProjectID"]
    labeling_config = config["labelstudio"]["LabelingConfig"]

    label_config = start_label_studio(label_studio_url, label_studio_api, label_studio_project_id, labeling_config)
    get_sample_prediction(label_config)