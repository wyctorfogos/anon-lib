import re
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
import ollama

class IntelligentAnonnimizer:
    def __init__(self,
            llm_model_name:str="hf.co/empero-ai/Qwen3.8-4B-Distill-GGUF:Q4_K_M",
            llm_ipaddress_service:str="http://localhost:11434/v1",
            language="pt-br"
        ):
        self.llm_model_name=llm_model_name
        self.llm_ipaddress_service=llm_ipaddress_service
        self.language=language
        # A ORDEM DE DECLARAÇÃO É A PRIORIDADE: quando dois padrões casam com o mesmo
        # valor, o primeiro declarado fica com ele. Por isso os padrões formatados
        # (mais específicos) vêm primeiro e os numéricos "crus" (mais ambíguos) por último.
        self._patterns_by_language={
            "pt-br" : {
                # --- Contato ---
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                # --- Financeiro (chave PIX aleatória = UUID v4) ---
                "CHAVE_PIX_ALEATORIA": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                # --- Documentos formatados ---
                # CPF cobre as duas formas numa tag só e está declarado lá embaixo,
                # junto dos numéricos crus: 11 dígitos sem pontuação são ambíguos e
                # não podem ter prioridade sobre TELEFONE_BR e CNH.
                "CNPJ_NUMERICO_FORMATADO": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
                "CNPJ_ALFANUMERICO": r"\b[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-\d{2}\b",
                "RG": r"\b\d{2}\.\d{3}\.\d{3}-[0-9Xx]\b",
                "PIS_PASEP": r"\b\d{3}\.\d{5}\.\d{2}-\d\b",
                # --- Contato / endereço ---
                "CEP": r"(?<!\d)\d{5}-\d{3}(?!\d)",
                # --- Outros identificadores ---
                # Casa qualquer data dd/mm/aaaa: o regex não distingue data de
                # nascimento de outras datas (isso exige contexto, papel do LLM).
                "DATA_NASCIMENTO": r"\b\d{2}/\d{2}/\d{4}\b",
                "PLACA_VEICULO_MERCOSUL": r"\b[A-Z]{3}\d[A-Z]\d{2}\b",
                "PLACA_VEICULO": r"\b[A-Z]{3}[- ]?\d{4}\b",
                # --- Financeiro ---
                "CARTAO_CREDITO_AMEX": r"(?<!\d)3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}(?!\d)",
                "CARTAO_CREDITO": r"(?<!\d)(?:\d{4}[ .-]?){3}\d{4}(?!\d)",
                "IP": r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d)",
                # Ancorados por rótulo: o número sozinho é indistinguível de CPF/telefone,
                # então só marcamos como CNH/agência/conta quando o rótulo está presente.
                # O rótulo entra no trecho mascarado.
                "CNH": r"(?i)\bCNH\s*n?[º°]?\s*:?\s*\d{11}\b",
                "AGENCIA": r"(?i)\bag(?:[êe]ncia)?\.?\s*n?[º°]?\s*:?\s*\d{4}(?:-\d)?\b",
                "CONTA_BANCARIA": r"(?i)\b(?:c\/c|cc|conta)\.?\s*n?[º°]?\s*:?\s*\d{4,12}-?\d?\b",
                # --- Numéricos crus (mais ambíguos, por último) ---
                "TELEFONE_BR": r"(?<!\d)(?:\+55[-. ]?)?\(?\d{2}\)?[-. ]?9?\d{4}[-. ]?\d{4}(?!\d)",
                "TITULO_ELEITOR": r"(?<!\d)\d{4}[ .]?\d{4}[ .]?\d{4}(?!\d)",
                "CNPJ_NUMERICO": r"\b\d{14}\b",
                "CNPJ_ALFANUMERICO_SEM_PONTUACAO": r"\b[A-Z0-9]{12}\d{2}\b",
                # Uma única tag <CPF_n> para as duas formas: 123.456.789-00 e 12345678901.
                # Usa (?<!\d)...(?!\d) em vez de \b no ramo sem pontuação porque \b
                # falharia em "_12345678901" ("_" é caractere de palavra).
                "CPF": r"\b\d{3}\.\d{3}\.\d{3}[.-]\d{2}\b|(?<!\d)\d{11}(?!\d)",
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
    @property
    def list_of_words_patterns(self):
        try:
            # Obtém a lista de padrões a serem procurados
            lista_por_idioma=self._patterns_by_language.get(self.language)
            if lista_por_idioma is None:
                raise ValueError(f"Idioma '{self.language}' não suportado.")
            return lista_por_idioma
        except Exception as e:
            raise ValueError(f"Erro ao obter a lista de padrões: {e}")
    def split_setences(self, sentence_text:str):
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", ".", " ", ""],  # Paragraph → Line → Sentence → Word → Character
                chunk_size=1000,
                # por valor em find_keywords_and_replace.
                chunk_overlap=50
            )
            return text_splitter.split_text(sentence_text)
        except Exception as e:
            raise ValueError(f"Erro ao realizar o split das sentenças textuais: {e}") from e

    def find_keywords_and_replace(self, chunks_of_sentence_text:str=None):
        if not chunks_of_sentence_text:
            raise ValueError(f"Sem sentença a análisar.")

        dict_found_keywords={}
        valores_ja_capturados=set()
        for chunk in chunks_of_sentence_text:
            for pii_type, pattern in self.list_of_words_patterns.items():
                for match in re.finditer(pattern, chunk):
                    valor=match.group(0)
                    # Um mesmo valor pode casar com vários padrões (ex.: 11 dígitos
                    # crus são CPF e telefone ao mesmo tempo). Vence o primeiro
                    # padrão declarado, que é o mais específico.
                    if valor in valores_ja_capturados:
                        continue
                    valores_ja_capturados.add(valor)
                    dict_found_keywords.setdefault(pii_type, set()).add(valor)
        return dict_found_keywords

    def anonimize_text(self, sentence_text:str):
        try:
            # Obtém as palavras chaves
            chuncks = self.split_setences(sentence_text=sentence_text)
            # Encontra as palavras a serem encontradas
            pii_words = self.find_keywords_and_replace(chunks_of_sentence_text=chuncks)
            # Substitui as palavras encontradas por tags únicas
            dict_unique_tags={}
            for pii_type, values in pii_words.items():
                # sorted() garante numeração de tags estável entre execuções
                # (a ordem de iteração de um set de strings varia por processo).
                for index, value in enumerate(sorted(values)):
                    tag=f"<{pii_type}_{index}>"
                    dict_unique_tags[tag]=value
            masked_text=sentence_text
            for tag, original_value in sorted(dict_unique_tags.items(), key=lambda item: len(item[1]), reverse=True):
                masked_text=re.sub(pattern=re.escape(original_value), repl=tag, string=masked_text)
            return masked_text
        except Exception as e:
            raise ValueError(f"Erro ao anonimizar a sentença: {e}") from e
