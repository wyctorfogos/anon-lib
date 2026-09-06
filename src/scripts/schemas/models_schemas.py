import pydantic
from pydantic import BaseModel
from typing_extensions import List, Dict

class AnonOutput(BaseModel):
    anon_model_output: List[Dict]