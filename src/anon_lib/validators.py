"""Validacao de digito verificador, aplicada como filtro pos-regex (strict=True)."""
import re


def _alnum(valor: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", valor).upper()


def luhn_check(valor: str) -> bool:
    digitos = [int(c) for c in valor if c.isdigit()]
    if not 13 <= len(digitos) <= 19:
        return False
    soma = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
    return soma % 10 == 0


def cpf_validate(valor: str) -> bool:
    d = re.sub(r"\D", "", valor)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def cnpj_validate(valor: str) -> bool:
    """Aceita o CNPJ numerico e o alfanumerico (valor do caractere = ord - 48)."""
    c = _alnum(valor)
    if len(c) != 14 or not c[12:].isdigit() or c == c[0] * 14:
        return False
    vals = [ord(ch) - 48 for ch in c]
    for n, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
                     (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        resto = sum(v * p for v, p in zip(vals, pesos)) % 11
        if (0 if resto < 2 else 11 - resto) != vals[n]:
            return False
    return True


VALIDATORS = {
    "CPF": cpf_validate,
    "CNPJ_NUMERICO_FORMATADO": cnpj_validate,
    "CNPJ_ALFANUMERICO": cnpj_validate,
    "CNPJ_NUMERICO": cnpj_validate,
    "CNPJ_ALFANUMERICO_SEM_PONTUACAO": cnpj_validate,
    "CARTAO_CREDITO": luhn_check,
    "CARTAO_CREDITO_AMEX": luhn_check,
    "CREDIT_CARD": luhn_check,
    "CREDIT_CARD_AMEX": luhn_check,
}
