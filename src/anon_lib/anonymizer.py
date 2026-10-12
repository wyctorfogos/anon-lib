import re
import copy
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from anon_lib.patterns.patterns import _patterns_by_language
from anon_lib.validators import VALIDATORS
from anon_lib.entities import RecognizedEntity


class Anonymizer:
    def __init__(self,
            llm_model_name:str="hf.co/empero-ai/Qwen3.8-4B-Distill-GGUF:Q4_K_M",
            llm_ipaddress_service:str="http://localhost:11434",
            language="pt-br",
            strict:bool=False,
            tag_style:str="index",
            deny_list=None,
            deny_list_ignore_case:bool=True
        ):
        self.llm_model_name=llm_model_name
        self.llm_ipaddress_service=llm_ipaddress_service
        self._llm_client_instance = None
        self.language=language
        # strict=True: descarta matches com digito verificador invalido (CPF, CNPJ,
        # cartao/Luhn); o valor cai para o proximo padrao da lista, se houver.
        self.strict=strict
        # tag_style="index": [CPF_0], posicional (muda conforme os outros valores do texto).
        # tag_style="hash":  [CPF_a1b2c3d4], derivada do valor; o mesmo valor recebe a
        # mesma tag em qualquer texto e em qualquer processo.
        if tag_style not in ("index", "hash"):
            raise ValueError("tag_style deve ser 'index' ou 'hash'.")
        self.tag_style=tag_style
        self._patterns_by_language=_patterns_by_language
        # deny_list: termos sensiveis proprios do usuario. Aceita uma lista de
        # termos (tipo "DENY_LIST") ou {tipo: [termos]}. Tem prioridade sobre
        # os padroes regex: um trecho coberto por ela nao e reanalisado.
        self.deny_list_ignore_case=deny_list_ignore_case
        self._deny_patterns=self._compile_deny_list(deny_list)
        self.list_of_undeterministics_entities = [
            "PERSON_NAME", "ADDRESS", "LOCATION", "ORGANIZATION", 
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

    @staticmethod
    def _require_llm():
        """Importa ollama/pydantic sob demanda: so o modo use_llm=True precisa deles."""
        try:
            import ollama
            from anon_lib.schemas.models_schemas import AnonOutput
        except ImportError as e:
            raise ImportError(
                "O modo LLM requer dependencias opcionais: pip install 'anon-lib[llm]'"
            ) from e
        return ollama, AnonOutput

    @property
    def _llm_client(self):
        if self._llm_client_instance is None:
            ollama, _ = self._require_llm()
            self._llm_client_instance = ollama.Client(host=self.llm_ipaddress_service)
        return self._llm_client_instance

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

    def _compile_deny_list(self, deny_list) -> list:
        if not deny_list:
            return []
        if not isinstance(deny_list, dict):
            deny_list = {"DENY_LIST": deny_list}
        flags = re.IGNORECASE if self.deny_list_ignore_case else 0
        compiladas = []
        for tipo, termos in deny_list.items():
            if isinstance(termos, str):
                raise ValueError(f"deny_list['{tipo}'] deve ser uma lista de termos, nao uma string.")
            termos = sorted({t.strip() for t in termos if t and t.strip()}, key=len, reverse=True)
            if termos:
                alternativas = "|".join(self._value_regex(t) for t in termos)
                compiladas.append((tipo, re.compile(alternativas, flags)))
        return compiladas

    def _scan_regex(self, text: str, owner: dict = None):
        """Varre `text` com os padroes do idioma, em ordem de prioridade.

        `owner` mapeia valor -> tipo que o capturou primeiro: o mesmo valor
        nao muda de tipo (CPF sem pontuacao vs. telefone), mas se repete no
        mesmo tipo em todas as posicoes.
        """
        owner = {} if owner is None else owner
        entidades = []
        # Trechos rejeitados pelo validador: padroes de menor prioridade nao
        # podem mascarar um pedaco deles (cartao invalido virando titulo).
        rejeitados = []
        # Trechos ja capturados pela deny-list (prioridade maxima).
        ocupados = []
        for pii_type, padrao in self._deny_patterns:
            for match in padrao.finditer(text):
                if any(match.start() < fim and inicio < match.end()
                       for inicio, fim in ocupados):
                    continue
                valor = match.group(0)
                if owner.setdefault(valor, pii_type) != pii_type:
                    continue
                entidades.append(RecognizedEntity(
                    pii_type, valor, match.start(), match.end(), 1.0))
                ocupados.append(match.span())
        for pii_type, pattern in self.list_of_words_patterns.items():
            validador = VALIDATORS.get(pii_type)
            for match in re.finditer(pattern, text):
                valor = match.group(0)
                valido = validador(valor) if validador else True
                if not valido and self.strict:
                    rejeitados.append(match.span())
                    continue
                if any(match.start() < fim and inicio < match.end()
                       for inicio, fim in rejeitados + ocupados):
                    continue
                if owner.setdefault(valor, pii_type) != pii_type:
                    continue
                entidades.append(RecognizedEntity(
                    pii_type, valor, match.start(), match.end(),
                    1.0 if valido else 0.5,
                ))
        return entidades

    def find_keywords_and_replace(self, chunks_of_sentence_text:str=None):
        if not chunks_of_sentence_text:
            raise ValueError(f"Sem sentença a análisar.")

        dict_found_keywords={}
        owner={}
        for chunk in chunks_of_sentence_text:
            for e in self._scan_regex(chunk, owner):
                dict_found_keywords.setdefault(e.type, set()).add(e.value)
        return dict_found_keywords

    def analyze(self, sentence_text: str, use_llm: bool = False, min_score: float = 0.0):
        """Devolve as entidades encontradas, sem mascarar o texto.

        Cada RecognizedEntity traz tipo, valor, offsets [start, end) e score.
        Ordenadas por posicao. O regex vence o LLM em trechos sobrepostos.
        """
        if not sentence_text or not sentence_text.strip():
            raise ValueError("Sem sentença a análisar.")
        entidades = self._scan_regex(sentence_text)

        if use_llm:
            ocupados = [(e.start, e.end) for e in entidades]
            for tipo, valores in self.find_undeterministic_entities(sentence_text).items():
                for valor in sorted(valores):
                    for m in re.finditer(self._value_regex(valor), sentence_text):
                        if any(m.start() < fim and inicio < m.end() for inicio, fim in ocupados):
                            continue
                        entidades.append(RecognizedEntity(tipo, valor, m.start(), m.end(), 0.8))
                        ocupados.append(m.span())

        entidades = [e for e in entidades if e.score >= min_score]
        return sorted(entidades, key=lambda e: (e.start, -e.end))

    def get_llm_response(self, prompt:str, format_schema:dict=None):
        _, AnonOutput = self._require_llm()
        try:
            response = self._llm_client.chat(
                model=self.llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                format=format_schema or AnonOutput.model_json_schema(),
                options={"temperature": 0}
            )
            return response
        except Exception as e:
            raise ValueError(f"Erro ao obter resposta do LLM: {e}") from e
        
    def find_undeterministic_entities(self, sentence_text:str):
        _, AnonOutput = self._require_llm()
        prompt = (
            f"{self.prompt}\n\n"
            f"Tipos de entidade a procurar:\n"
            f"{', '.join(self.list_of_undeterministics_entities)}\n\n"
            f"Ignore estes tipos, já tratados por regex:\n"
            f"{', '.join(self.list_of_words_patterns)}\n\n"
            f"Texto:\n{sentence_text.strip()}"
        )

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
            
    def _build_tags(self, pii_words: dict) -> dict:
        tags = {}
        for tipo, valores in pii_words.items():
            for i, valor in enumerate(sorted(valores)):
                if self.tag_style == "index":
                    tags[f"[{tipo}_{i}]"] = valor
                    continue
                digest = hashlib.sha256(valor.encode("utf-8")).hexdigest()
                tamanho = 8
                while f"[{tipo}_{digest[:tamanho]}]" in tags:  # colisao: alonga
                    tamanho += 4
                tags[f"[{tipo}_{digest[:tamanho]}]"] = valor
        return tags

    @staticmethod
    def _value_regex(valor: str) -> str:
        """Regex do valor literal, com fronteira de palavra nas pontas alfanumericas."""
        esq = r"(?<!\w)" if valor[0].isalnum() or valor[0] == "_" else ""
        dir_ = r"(?!\w)" if valor[-1].isalnum() or valor[-1] == "_" else ""
        return f"{esq}{re.escape(valor)}{dir_}"

    @staticmethod
    def _mask(text: str, tags: dict) -> str:
        """Substitui cada valor por sua tag numa unica passagem.

        Valores que comecam/terminam em caractere de palavra so casam em
        fronteira de palavra ("Ana" nao mascara dentro de "Mariana"). A
        alternancia em ordem decrescente de tamanho faz o valor mais longo
        vencer, e a passagem unica impede de mascarar o texto de uma tag ja
        inserida.
        """
        if not tags:
            return text
        por_valor = {valor: tag for tag, valor in tags.items()}
        alternativas = [Anonymizer._value_regex(valor)
                        for valor in sorted(por_valor, key=len, reverse=True)]
        return re.sub("|".join(alternativas), lambda m: por_valor[m.group(0)], text)

    def anonimize_text(self, sentence_text: str, use_llm: bool = False, min_score: float = 0.0):
        pii_words = {}
        for e in self.analyze(sentence_text, use_llm=use_llm, min_score=min_score):
            pii_words.setdefault(e.type, set()).add(e.value)

        tags = self._build_tags(pii_words)

        masked_text = self._mask(sentence_text, tags)

        return masked_text, {t: v for t, v in tags.items() if t in masked_text}