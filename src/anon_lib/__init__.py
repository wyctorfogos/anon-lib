"""Deteccao e mascaramento de PII em texto livre (pt-br e en).

Camada regex, deterministica e sem rede, opcionalmente somada a uma camada LLM
via Ollama para entidades que dependem de contexto (nomes, lugares, idades).
"""

from anon_lib.anonymizer import Anonymizer
from anon_lib.entities import RecognizedEntity

__all__ = ["Anonymizer", "RecognizedEntity"]
