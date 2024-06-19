from enum import Enum
from pydantic import BaseModel, create_model, Field, field_validator
from typing import List, Optional, Union, Literal, Type
from label_studio_sdk.label_interface import LabelInterface
from datetime import date



class LabelingTypes(str, Enum):
    """
    """
    CHOICES = "SINGLE_CHOICE"
    MULTIPLE_CHOICES = "MULTIPLE_CHOICES"
    TAXONOMY = "TAXONOMY"
    LABELS = "LABELS"
    SINGLE_TEXT = "SINGLE_TEXT"
    MULTIPLE_TEXTS = "MULTIPLE_TEXTS"


def get_pydantic_class(
    type: str,
    labels: Optional[List[str]],
) -> Type[BaseModel]:

    if type == 'Choices':
        model = create_model(
            type,
            output=(Enum('Choice', {l: l for l in labels}), ...),
        )
        model.__doc__ = "Classify the text into one of the given choices."

    elif type == 'ChoicesMultiple':
        model = create_model(
            type,
            output=(List[Enum('Choice', {l: l for l in labels})], ...),
        )
        model.__doc__ = "Classify the text into one or more of the given choices."

    elif type == 'Taxonomy':
        model = create_model(
            type,
            output=(List[List[Enum('Taxonomy', {l: l for l in labels})]], ...)
        )
        model.__doc__ = (f"Given the taxonomy of categories: {labels}, "
                         f"assign the text to one or more of the given categories.")
    elif type == "Labels":
        model = create_model(
            type,
            output=(Enum('Label', {l: l for l in labels}), ...),
            start=(int, ...),
            end=(int, ...),
        )
        model.__doc__ = ("Extract the entities from the text and assign them to the given labels. "
                         "Additionally, provide the start and end character indices of the entities.")
    elif type == "TextArea":
        model = create_model(
            type,
            output=(str, ...),
        )
        model.__doc__ = "Generate a text based on the given input."

    elif type == "TextAreaMultiple":
        model = create_model(
            type,
            output=(List[str], ...),
        )
        model.__doc__ = "Generate one or more texts based on the given input."

    elif type == "DateTime":
        model = create_model(
            type,
            output=(date, ...),
            # __validators__={
            #     # check that date in 'YYYY-MM-DD' format
            #     'output': field_validator('output')(lambda v: date.fromisoformat(v))
            # }
        )
        model.__doc__ = "Extract the date in the format YYYY-MM-DD. "

    elif type == "Number":
        model = create_model(
            type,
            output=(int, ...),
        )
        model.__doc__ = "Extract the number from the text."

    else:
        raise NotImplementedError(f"Type {type} is not supported.")

    # JSON former add-on
    model.__doc__ += "\n\nProvide output in the JSON format."

    return model


def parse_config_and_get_pydantic_labeling_model(
    config: str,
) -> Type[BaseModel]:

    li = LabelInterface(config)
    meta_model_fields = {}
    for annotation_tag in li.controls:
        type = annotation_tag.tag
        labels = list(annotation_tag.labels)
        annotation_class = get_pydantic_class(type, labels)
        meta_model_fields[annotation_tag.name] = (annotation_class, ...)

    model = create_model(
        'LabelingModel',
        **meta_model_fields,
    )
    return model


if __name__ == "__main__":
    config = """
    <View>
      <Choices name="label" toName="text" choice="single">
        <Choice value="label_A"></Choice>
        <Choice value="label_B"></Choice>
      </Choices>
      <DateTime name="datetime" toName="txt" only="date"/>
    <Number name="total_amount" toName="image" slider="true"
      prompt="Calculate the total amount paid."/>
    </View>
    """
    model = parse_config_and_get_pydantic_labeling_model(config)
    from sglang.srt.constrained import build_regex_from_object
    r = build_regex_from_object(model)
    print(model.schema())
    print(r)
