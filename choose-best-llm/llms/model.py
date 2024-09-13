import io
import json
import logging
import threading
import json
import os

from typing import List, Dict, Optional
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
from label_studio_sdk.label_interface import LabelInterface
from label_studio_sdk.label_interface.objects import PredictionValue
from labeliing_schemes import parse_config_and_get_pydantic_labeling_model
from sglang import function, system, user, assistant, gen, set_default_backend, RuntimeEndpoint
from sglang.srt.constrained import build_regex_from_object

logger = logging.getLogger(__name__)
LLMS = json.load(open(os.path.join(os.path.dirname(__file__), 'llms.json')))
print(f'Connected LLMs:\n{json.dumps(LLMS, indent=4)}')


class NewModel(LabelStudioMLBase):


    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        li = LabelInterface(self.label_config)
        ResponseModel = parse_config_and_get_pydantic_labeling_model(self.label_config)

        @function
        def gen_proc(s, context):
            s += system(ResponseModel.__doc__)
            s += user(context)
            s += assistant(gen(
                "value",
                max_tokens=128,
                temperature=0,
                regex=build_regex_from_object(ResponseModel),
            ))

        tasks_predictions = []
        for task in tasks:
            results = {}

            def predict_from_model(model_name, model_url, context):
                set_default_backend(RuntimeEndpoint(model_url))
                state = gen_proc.run(context=context)

                try:
                    value = json.loads(state['value'])
                except json.JSONDecodeError:
                    logger.error(f'Failed to decode JSON from model {model_name}: {state["value"]}')
                    value = None

                # thread safe lock
                with threading.Lock():
                    results[model_name] = value
                    logger.debug(f'Model {model_name} context: {context} -> {value}')

            prompt = 'Instructions:\n'
            for i, tag in enumerate(li.controls):
                tag_prompt = tag.attr.get('prompt')
                prompt += f'- {tag_prompt}\n'

            text = task['data']['text']
            context = f"{prompt}\n\nInput:\n{text}"

            threads = []
            for model_name, model_url in LLMS.items():
                t = threading.Thread(target=predict_from_model, args=(model_name, model_url, context))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            logger.info(f'Results: {results}')

            predictions = []
            for model_name, result in results.items():
                if not result:
                    logger.error(f'No result from model {model_name}')
                    continue
                model_prediction = PredictionValue(model_version=model_name, result=[])
                for tag_name, v in result.items():
                    if v:
                        control_tag = self.label_interface.get_control(tag_name)
                        control_type = control_tag.tag.lower()
                        # region = control_tag.label(**{control_type: v['output']})

                        object_tag = control_tag.get_object()
                        output = [v['output']] if control_type in ('choices', 'labels', 'textarea') else v['output']
                        key = control_type if control_type != 'textarea' else 'text'
                        model_prediction.result.append({
                            'from_name': control_tag.name,
                            'to_name': object_tag.name,
                            'type': control_type,
                            'value': {
                                key: output
                            }
                        })
                predictions.append(model_prediction)

            tasks_predictions.append(predictions)

        return ModelResponse(predictions=tasks_predictions)


