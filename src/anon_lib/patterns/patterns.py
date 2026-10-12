_patterns_by_language={
            "pt-br" : {
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "CHAVE_PIX_ALEATORIA": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                "CNPJ_NUMERICO_FORMATADO": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
                "CNPJ_ALFANUMERICO": r"\b[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-\d{2}\b",
                "RG": r"\b\d{2}\.\d{3}\.\d{3}-[0-9Xx]\b",
                "PIS_PASEP": r"\b\d{3}\.\d{5}\.\d{2}-\d\b",
                "CEP": r"(?<!\d)\d{5}-\d{3}(?!\d)",
                "DATA": r"\b\d{2}/\d{2}/\d{4}\b",
                "PLACA_VEICULO_MERCOSUL": r"\b[A-Z]{3}\d[A-Z]\d{2}\b",
                "PLACA_VEICULO": r"\b[A-Z]{3}[- ]?\d{4}\b",
                # --- Financeiro ---
                "CARTAO_CREDITO_AMEX": r"(?<!\d)3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}(?!\d)",
                "CARTAO_CREDITO": r"(?<!\d)(?:\d{4}[ .-]?){3}\d{4}(?!\d)",
                "IP": r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d)",
                "CNH": r"(?i)\bCNH\s*n?[º°]?\s*:?\s*\d{11}\b",
                "AGENCIA": r"(?i)\bag(?:[êe]ncia)?\.?\s*n?[º°]?\s*:?\s*\d{4}(?:-\d)?\b",
                "CONTA_BANCARIA": r"(?i)\b(?:c\/c|cc|conta)\.?\s*n?[º°]?\s*:?\s*\d{4,12}-?\d?\b",
                # --- Numéricos crus (mais ambíguos, por último) ---
                "TELEFONE_BR": r"(?<!\d)(?:\+55[-. ]?)?\(?\d{2}\)?[-. ]?9?\d{4}[-. ]?\d{4}(?!\d)",
                "TITULO_ELEITOR": r"(?<!\d)\d{4}[ .]?\d{4}[ .]?\d{4}(?!\d)",
                "CNPJ_NUMERICO": r"\b\d{14}\b",
                "CNPJ_ALFANUMERICO_SEM_PONTUACAO": r"\b[A-Z0-9]{12}\d{2}\b",
                "CPF": r"\b\d{3}\.\d{3}\.\d{3}[.-]\d{2}\b|(?<!\d)\d{11}(?!\d)",
            },
            "fr": {
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "IBAN_FR": r"\bFR\d{2}(?:[ ]?[0-9A-Z]{4}){5}[ ]?[0-9A-Z]{3}\b",
                "NIR": r"(?<!\d)[12][ .]?\d{2}[ .]?\d{2}[ .]?(?:\d{2}|2[AB])[ .]?\d{3}[ .]?\d{3}[ .]?\d{2}(?!\d)",
                "SIRET": r"(?<!\d)\d{3}[ .]?\d{3}[ .]?\d{3}[ .]?\d{5}(?!\d)",
                "SIREN": r"(?<!\d)\d{3}[ .]?\d{3}[ .]?\d{3}(?![ .]?\d)",
                "CARTE_BANCAIRE_AMEX": r"(?<!\d)3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}(?!\d)",
                "CARTE_BANCAIRE": r"(?<!\d)(?:\d{4}[ .-]?){3}\d{4}(?!\d)",
                "IP": r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d)",
                "DATE": r"\b\d{2}/\d{2}/\d{4}\b",
                "CARTE_IDENTITE": r"(?i)\b(?:CNI|carte\s+(?:nationale\s+)?d['’]identité)\s*(?:n[º°o]\s*)?:?\s*[0-9A-Z]{12}\b",
                # --- Numéricos crus (mais ambíguos, por último) ---
                "TELEPHONE_FR": r"(?<!\d)(?:(?:\+|00)33[ .-]?\(?0?\)?|0)[1-9](?:[ .-]?\d{2}){4}(?!\d)",
                "CODE_POSTAL": r"(?<!\d)(?:0[1-9]|[1-8]\d|9[0-5]|97|98)\d{3}(?!\d)",
            },
            "en": {
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "SSN": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
                "CREDIT_CARD_AMEX": r"(?<!\d)3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}(?!\d)",
                "CREDIT_CARD": r"(?<!\d)(?:\d{4}[ .-]?){3}\d{4}(?!\d)",
                "IP": r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d)",
                "US_PHONE": r"(?<!\d)(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})(?!\d)",
                "US_ZIP": r"\b\d{5}(?:-\d{4})?\b"
            }
        }