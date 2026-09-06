import re
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
import sys
sys.path.append("../")
from schemas.models_schemas import AnonymizationResult
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
        self._patterns_by_language={
            "pt-br" : {
                "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "CHAVE_PIX_ALEATORIA": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                "CNPJ_NUMERICO_FORMATADO": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
                "CNPJ_ALFANUMERICO": r"\b[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-\d{2}\b",
                "RG": r"\b\d{2}\.\d{3}\.\d{3}-[0-9Xx]\b",
                "PIS_PASEP": r"\b\d{3}\.\d{5}\.\d{2}-\d\b",
                "CEP": r"(?<!\d)\d{5}-\d{3}(?!\d)",
                "DATA_NASCIMENTO": r"\b\d{2}/\d{2}/\d{4}\b",
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
        self.list_of_undeterministics_entities = ["PERSON_NAME", "LOCATION", "ORGANIZATION", "DATE", "TIME", "MONEY", "PERCENT", "FACILITY", "GPE"]
        self.prompt = f"Detecte e substitua informações pessoais identificáveis (PII) no texto abaixo por tags únicas. Retorne apenas o texto modificado, sem explicações adicionais.\n\n.Lista com padrões de PII para o idioma selecionado:\n{self.list_of_words_patterns()}\n\n Texto: "

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
                    if valor in valores_ja_capturados:
                        continue
                    valores_ja_capturados.add(valor)
                    dict_found_keywords.setdefault(pii_type, set()).add(valor)
        return dict_found_keywords
    
    def get_llm_response(self, prompt:str):
        try:
            response = ollama.chat(
                model=self.llm_model_name,
                prompt=prompt,
                host=self.llm_ipaddress_service,
                format=AnonymizationResult.model_json_format()
            )
            return response
        except Exception as e:
            raise ValueError(f"Erro ao obter resposta do LLM: {e}") from e
        
    def get_llm_response_text(self, text:str):
        # Busca a resposta do LLM e retorna apenas o texto, lidando com possíveis erros.
        self.prompt = f"Detecte e substitua informações pessoais identificáveis (PII) no texto abaixo por tags únicas. Retorne apenas o texto modificado, sem explicações adicionais.\n\n. Lista com padrões de PII para o idioma selecionado{self.llm_model_name}. Lista de entidades não determinísticas\n{self.list_of_undeterministics_entities}\n\n Texto: {text.strip()}"
        text = self.prompt+"\n"+text.strip()

        try:
            response = self.get_llm_response(prompt=text)
            if not response or not hasattr(response, 'text'):
                raise ValueError("Resposta do LLM inválida ou vazia.")
            return response.text
        except Exception as e:
            raise ValueError(f"Erro ao obter texto da resposta do LLM: {e}") from e
            
    def anonimize_text(self, sentence_text:str):
        try:
            # Obtém as palavras chaves
            chuncks = self.split_setences(sentence_text=sentence_text)
            # Encontra as palavras a serem encontradas
            pii_words = self.find_keywords_and_replace(chunks_of_sentence_text=chuncks)
            print(f"Palavras encontradas: {pii_words}")
            # Substitui as palavras encontradas por tags únicas
            dict_unique_tags={}
            for pii_type, values in pii_words.items():
                for index, value in enumerate(sorted(values)):
                    tag=f"<{pii_type}_{index}>"
                    dict_unique_tags[tag]=value
            masked_text=sentence_text
            for tag, original_value in sorted(dict_unique_tags.items(), key=lambda item: len(item[1]), reverse=True):
                masked_text=re.sub(pattern=re.escape(original_value), repl=tag, string=masked_text)
            return masked_text
        except Exception as e:
            raise ValueError(f"Erro ao anonimizar a sentença: {e}") from e