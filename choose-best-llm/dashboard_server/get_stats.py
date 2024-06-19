import os

from tqdm import tqdm
import difflib
from collections import defaultdict


def is_matching(pred, gt):
    label_type = list(pred.keys())[0]
    if label_type in ('choices', 'datetime'):
        return pred == gt
    elif label_type == 'number':
        return abs(pred['number'] - gt['number']) < 5
    elif label_type == 'text':
        return difflib.SequenceMatcher(None, pred['text'], gt['text']).ratio() > 0.8
    else:
        raise NotImplementedError(f"Label type {label_type} is not supported")


def get_stats_from_label_studio(project_id):
    from label_studio_sdk.client import LabelStudio

    ls = LabelStudio(
        base_url=os.getenv('LABEL_STUDIO_BASE_URL'),
        api_key=os.getenv('LABEL_STUDIO_API_KEY')
    )

    project = ls.projects.get(project_id)
    total_tasks = project.task_number
    total_annotations = project.total_annotations_number
    project_title = project.title
    print(f"Project '{project_title}' has {total_annotations} annotations")

    # model correct predictions counters
    correct_predictions = {}

    for task in tqdm(ls.tasks.list(project=project_id, fields='all'), total=total_tasks):
        if task.annotations and task.predictions and not task.annotations[0]['was_cancelled']:
            gt = {}
            for region in task.annotations[0]['result']:
                gt[region['from_name']] = region['value']
                if region['from_name'] not in correct_predictions:
                    correct_predictions[region['from_name']] = defaultdict(int)
            for prediction in task.predictions:
                model_version = prediction['model_version']
                for from_name, gt_value in gt.items():
                    # find the region with the same name as the ground truth
                    pred_region = next((region for region in prediction['result'] if region['from_name'] == from_name), None)
                    if pred_region and is_matching(pred_region['value'], gt_value):
                        correct_predictions[from_name][model_version] += 1
                    else:
                        correct_predictions[from_name][model_version] += 0

    # calculate accuracy
    accuracy = {
        region: {
            model: correct_predictions[region][model] / total_annotations
            for model in correct_predictions[region]
        }
        for region in correct_predictions
    }
    return accuracy


if __name__ == "__main__":
    import sys
    import json
    # get project id from arguments
    project_id = int(sys.argv[1])
    stats = get_stats_from_label_studio(project_id)
    print(json.dumps(stats, indent=4))
