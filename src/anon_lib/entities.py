from dataclasses import dataclass


@dataclass(frozen=True)
class RecognizedEntity:
    """Uma PII localizada no texto: o trecho [start, end) tem o valor `value`.

    score: 1.0 para regex exato (ou com digito verificador valido); 0.5 para
    regex cujo digito verificador e invalido (so ocorre com strict=False);
    0.8 fixo para o LLM, que nao expoe confianca por entidade.
    """

    type: str
    value: str
    start: int
    end: int
    score: float = 1.0
