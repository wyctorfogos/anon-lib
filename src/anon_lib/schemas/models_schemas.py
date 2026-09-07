from typing import List

from pydantic import BaseModel, Field


class PIIEntity(BaseModel):
    """Uma entidade PII localizada pelo LLM no texto."""

    tipo: str = Field(description="Tipo da entidade: PERSON, AGE, ADDRESS, ...")
    valor: str = Field(description="Trecho exato copiado do texto, sem reescrever")


class AnonOutput(BaseModel):
    """Saída estruturada esperada do LLM.

    É uma lista de objetos, e não um dict {tipo: valor}, porque um dict não pode
    repetir a mesma chave: um texto com duas pessoas perderia uma delas em
    silêncio (é o mesmo defeito do exemplo de saída que está no README).
    """

    anon_model_output: List[PIIEntity]
