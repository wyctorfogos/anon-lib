import re
import os
import copy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from anon_lib.patterns.patterns import _patterns_by_language

class Anonymizer:
    def __init__(self,
            llm_model_name:str="hf.co/empero-ai/Qwen3.8-4B-Distill-GGUF:Q4_K_M",
            llm_ipaddress_service:str="http://localhost:11434",
            language="pt-br"
        ):
        self.llm_model_name=llm_model_name
        self.llm_ipaddress_service=llm_ipaddress_service
        self._llm_client=None  # criado sob demanda; veja _require_llm()
        self.language=language
        self._patterns_by_language=_patterns_by_language
        self.list_of_undeterministics_entities = [
            "PERSON_NAME", "LOCATION", "ORGANIZATION", 
            "DATE", "AGE",
            "TIME", "MONEY", "PERCENT", "FACILITY", "GPE"
        ]

        self.prompt = (
            "Você é um detector de dados pessoais (PII). Devolva as entidades "
            "encontradas no texto em JSON, seguindo o schema pedido.\n"
            "Regras:\n"
            "- Copie cada valor exatamente como aparece no texto, sem reescrever.\n"
            "- Não devolva o texto mascarado: quem mascara é o código.\n"
            "- Se não houver nenhuma entidade, devolva uma lista vazia.\n"
            "- Capture TODOS os nomes de pessoas, incluindo terceiros mencionados "
            "por vínculo familiar, profissional ou social "
            "(ex: 'pai de', 'filha de', 'cônjuge de', 'advogado de').\n"
            "- Capture idades expressas como número seguido de 'anos' "
            "(ex: '35 anos', 'com 12 anos') como entidade do tipo AGE."
        )

    def _require_llm(self):
        """Carrega as dependencias opcionais do modo LLM e devolve (client, schema).

        Erro de import vira mensagem acionavel: sem isso o usuario receberia um
        ModuleNotFoundError cru, sem pista de que existe um extra a instalar.
        """
        try:
            import ollama
            from anon_lib.schemas.models_schemas import AnonOutput
        except ImportError as e:
            raise ImportError(
                "use_llm=True requer as dependencias opcionais do modo LLM: "
                "pip install anon-lib[llm]"
            ) from e
        if self._llm_client is None:
            self._llm_client = ollama.Client(host=self.llm_ipaddress_service)
        return self._llm_client, AnonOutput

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
                separators=["\n\n", "\n", ".", " ", ""],
                chunk_size=1000,
                chunk_overlap=100
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
    
    def get_llm_response(self, prompt:str, format_schema:dict=None):
        client, AnonOutput = self._require_llm()
        try:
            response = client.chat(
                model=self.llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                format=format_schema or AnonOutput.model_json_schema(),
                options={"temperature": 0}
            )
            return response
        except Exception as e:
            raise ValueError(f"Erro ao obter resposta do LLM: {e}") from e
        
    def find_undeterministic_entities(self, sentence_text:str):
        prompt = (
            f"{self.prompt}\n\n"
            f"Tipos de entidade a procurar:\n"
            f"{', '.join(self.list_of_undeterministics_entities)}\n\n"
            f"Ignore estes tipos, já tratados por regex:\n"
            f"{', '.join(self.list_of_words_patterns)}\n\n"
            f"Texto:\n{sentence_text.strip()}"
        )

        _, AnonOutput = self._require_llm()
        schema = copy.deepcopy(AnonOutput.model_json_schema())
        schema["$defs"]["PIIEntity"]["properties"]["tipo"]["enum"] = list(
            self.list_of_undeterministics_entities
        )
        response = self.get_llm_response(prompt=prompt, format_schema=schema)

        conteudo = getattr(response.message, "content", None)
        if not conteudo:
            raise ValueError("Resposta do LLM veio vazia.")
        try:
            resultado = AnonOutput.model_validate_json(conteudo)
        except Exception as e:
            raise ValueError(f"Resposta do LLM não bate com o schema: {e}") from e

        entidades = {}
        for entidade in resultado.anon_model_output:
            if entidade.valor and entidade.valor in sentence_text:
                entidades.setdefault(entidade.tipo, set()).add(entidade.valor)
        return entidades
            
    def anonimize_text(self, sentence_text: str, use_llm: bool = False):
        chunks = self.split_setences(sentence_text=sentence_text)
        pii_words = self.find_keywords_and_replace(chunks_of_sentence_text=chunks)

        if use_llm:
            ja_capturados = {v for valores in pii_words.values() for v in valores}
            for tipo, valores in self.find_undeterministic_entities(sentence_text).items():
                novos = {v for v in valores
                        if not any(v in j or j in v for j in ja_capturados)}
                if novos:
                    pii_words.setdefault(tipo, set()).update(novos)

        tags = {
            f"[{tipo}_{i}]": valor
            for tipo, valores in pii_words.items()
            for i, valor in enumerate(sorted(valores))
        }

        masked_text = sentence_text
        for tag, valor in sorted(tags.items(), key=lambda kv: len(kv[1]), reverse=True):
            masked_text = masked_text.replace(valor, tag)

        return masked_text, {t: v for t, v in tags.items() if t in masked_text}