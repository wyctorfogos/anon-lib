import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from anon_lib.inteligent_anon import Anonymizer

@pytest.fixture(scope="module")
def anon_ptbr():
    return Anonymizer(language="pt-br")


@pytest.fixture(scope="module")
def anon_en():
    return Anonymizer(language="en")


def mascarar(anon, texto, **kwargs):
    """anonimize_text devolve (texto_mascarado, tags); aqui interessa so o texto."""
    return anon.anonimize_text(texto, **kwargs)[0]


# --------------------------------------------------------------------------
# Um caso por padrão declarado em pt-br
# --------------------------------------------------------------------------
CASOS_PTBR = [
    ("Contato: joao.silva@empresa.com.br", "Contato: [EMAIL_0]"),
    ("Pix: 550e8400-e29b-41d4-a716-446655440000", "Pix: [CHAVE_PIX_ALEATORIA_0]"),
    ("CPF 123.345.123-45", "CPF [CPF_0]"),
    ("CNPJ 12.345.678/0001-99", "CNPJ [CNPJ_NUMERICO_FORMATADO_0]"),
    ("CNPJ 12.ABC.345/01DE-35", "CNPJ [CNPJ_ALFANUMERICO_0]"),
    ("RG 12.345.678-9", "RG [RG_0]"),
    ("PIS 123.45678.90-1", "PIS [PIS_PASEP_0]"),
    ("CEP 01310-100", "CEP [CEP_0]"),
    ("Nasceu em 05/09/1990", "Nasceu em [DATA_0]"),
    ("Placa ABC1D23", "Placa [PLACA_VEICULO_MERCOSUL_0]"),
    ("Placa ABC-1234", "Placa [PLACA_VEICULO_0]"),
    ("Cartao 4111 1111 1111 1111", "Cartao [CARTAO_CREDITO_0]"),
    ("Amex 3782 822463 10005", "Amex [CARTAO_CREDITO_AMEX_0]"),
    ("Servidor 192.168.0.14", "Servidor [IP_0]"),
    ("Ligue (11) 98765-4321", "Ligue [TELEFONE_BR_0]"),
    ("Ligue +55 11 98765-4321", "Ligue [TELEFONE_BR_0]"),
    ("Ligue 1134567890", "Ligue [TELEFONE_BR_0]"),
    ("Titulo 1234 5678 9012", "Titulo [TITULO_ELEITOR_0]"),
    ("CNPJ 12345678000199", "CNPJ [CNPJ_NUMERICO_0]"),
    ("CPF 12345678901", "CPF [CPF_0]"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_PTBR)
def test_padroes_ptbr(anon_ptbr, texto, esperado):
    assert mascarar(anon_ptbr, texto) == esperado


CASOS_EN = [
    ("Email me at jane.doe@example.com", "Email me at [EMAIL_0]"),
    ("SSN 123-45-6789", "SSN [SSN_0]"),
    ("Card 4111-1111-1111-1111", "Card [CREDIT_CARD_0]"),
    ("Amex 3782 822463 10005", "Amex [CREDIT_CARD_AMEX_0]"),
    ("Server 192.168.0.14", "Server [IP_0]"),
    ("ZIP 90210", "ZIP [US_ZIP_0]"),
    ("ZIP 90210-1234", "ZIP [US_ZIP_0]"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_EN)
def test_padroes_en(anon_en, texto, esperado):
    assert mascarar(anon_en, texto) == esperado


def test_telefone_en_preserva_pontuacao_de_abertura(anon_en):
    """O \\b inicial fazia o '(' e o '+' ficarem de fora do match."""
    assert mascarar(anon_en, "Call (415) 555-2671 now") == "Call [US_PHONE_0] now"
    assert mascarar(anon_en, "Call +1-415-555-2671 now") == "Call [US_PHONE_0] now"


# --------------------------------------------------------------------------
# Padrões ancorados por rótulo: o rótulo entra no trecho mascarado
# --------------------------------------------------------------------------
CASOS_COM_ROTULO = [
    ("CNH: 12345678901", "[CNH_0]"),
    ("Agencia 0001-2", "[AGENCIA_0]"),
    ("conta 123456-7", "[CONTA_BANCARIA_0]"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_COM_ROTULO)
def test_padroes_ancorados_por_rotulo(anon_ptbr, texto, esperado):
    assert mascarar(anon_ptbr, texto) == esperado


# --------------------------------------------------------------------------
# Resolução de conflito entre padrões
# --------------------------------------------------------------------------
def test_cartao_vence_titulo_de_eleitor(anon_ptbr):
    """Os 12 primeiros dígitos de um cartão espaçado casam com TITULO_ELEITOR.

    Se o valor curto fosse substituído primeiro, o cartão seria corrompido.
    """
    saida = mascarar(anon_ptbr, "Cartao 1234 5678 9012 3456 pago hoje")
    assert saida == "Cartao [CARTAO_CREDITO_0] pago hoje"


def test_cnpj_numerico_tem_prioridade_sobre_alfanumerico(anon_ptbr):
    """[A-Z0-9] também casa dígitos: o padrão numérico precisa vir antes."""
    assert "[CNPJ_NUMERICO_FORMATADO_0]" in mascarar(anon_ptbr, "12.345.678/0001-99")
    assert "[CNPJ_NUMERICO_0]" in mascarar(anon_ptbr, "12345678000199")


def test_sem_chaves_duplicadas_no_dicionario_de_padroes():
    """Chave repetida num dict literal é sobrescrita em silêncio.

    Não dá para detectar em runtime: o Python já descartou a duplicata na análise
    sintática. Por isso lemos a AST do fonte. Este bug já apagou padrões duas
    vezes (as 4 chaves "CNPJ", depois um segundo "CPF" que matou o formatado).
    """
    import ast

    import anon_lib.models
    from anon_lib import inteligent_anon

    # Varre os dois: o dicionário de padrões mora no __init__.py do pacote, e a
    # lógica no inteligent_anon.py. Olhar só um deixaria o outro desprotegido.
    duplicadas = []
    for modulo in (anon_lib.models, inteligent_anon):
        with open(modulo.__file__, encoding="utf-8") as arquivo:
            arvore = ast.parse(arquivo.read())
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Dict):
                continue
            chaves = [
                k.value for k in no.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            duplicadas += sorted({
                f"{os.path.basename(modulo.__file__)}:{c}"
                for c in chaves if chaves.count(c) > 1
            })

    assert duplicadas == [], f"chaves duplicadas apagam padroes: {duplicadas}"


def test_cpf_cobre_as_duas_formas_com_a_mesma_tag(anon_ptbr):
    assert mascarar(anon_ptbr, "CPF 123.456.789-00") == "CPF [CPF_0]"
    assert mascarar(anon_ptbr, "CPF 12345678901") == "CPF [CPF_0]"


def test_telefone_tem_prioridade_sobre_cpf_sem_pontuacao(anon_ptbr):
    """11 dígitos crus são ambíguos; o padrão de celular é o mais específico."""
    assert mascarar(anon_ptbr, "Ligue 11987654321") == "Ligue [TELEFONE_BR_0]"


def test_dotted_quad_invalido_como_ip_cai_em_cpf(anon_ptbr):
    """345 > 255, então não é IP; o CPF com separador tolerante pega."""
    assert mascarar(anon_ptbr, "Doc 123.345.123.45") == "Doc [CPF_0]"


def test_valor_curto_contido_em_valor_longo_nao_vaza_isolado(anon_ptbr):
    """O número da CNH rotulada também aparece solto: as duas ocorrências somem."""
    saida = mascarar(anon_ptbr, "CNH: 12345678901 e de novo 12345678901 aqui")
    assert "12345678901" not in saida


# --------------------------------------------------------------------------
# Fronteira de chunk (chunk_overlap)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("alvo", ["joao.silva@empresa.com.br", "123.345.123-45"])
def test_pii_na_fronteira_entre_chunks(anon_ptbr, alvo):
    """Com chunk_overlap=0 o dado partido na fronteira dos 1000 chars vazava."""
    vazamentos = []
    for n in range(940, 1060):
        filler = ("palavra teste do documento. " * 200)[:n]
        texto = f"{filler} {alvo} fim do documento."
        if alvo in mascarar(anon_ptbr, texto):
            vazamentos.append(n)
    assert vazamentos == []


# --------------------------------------------------------------------------
# Comportamento geral
# --------------------------------------------------------------------------
def test_texto_sem_pii_fica_intacto(anon_ptbr):
    texto = "Reuniao marcada para a sala 3 do predio azul."
    assert mascarar(anon_ptbr, texto) == texto


def test_multiplos_valores_do_mesmo_tipo_recebem_tags_distintas(anon_ptbr):
    saida = mascarar(anon_ptbr, "CPF 111.222.333-44 e CPF 555.666.777-88")
    assert saida == "CPF [CPF_0] e CPF [CPF_1]"


def test_idioma_nao_suportado(anon_ptbr):
    anon = Anonymizer(language="fr")
    with pytest.raises(ValueError, match="não suportado"):
        mascarar(anon, "texto qualquer")


@pytest.mark.parametrize("entrada", [None, []])
def test_find_keywords_sem_conteudo(anon_ptbr, entrada):
    with pytest.raises(ValueError, match="Sem sentença"):
        anon_ptbr.find_keywords_and_replace(chunks_of_sentence_text=entrada)


def test_numeracao_de_tags_estavel_entre_processos():
    """Iterar um set de strings varia com o PYTHONHASHSEED; sorted() estabiliza."""
    script = (
        "from scripts.models.inteligent_anon import Anonymizer;"
        "print(Anonymizer(language='pt-br').anonimize_text("
        "'CPF 111.222.333-44, CPF 555.666.777-88, CPF 999.888.777-66'))"
    )
    # Herda o sys.path deste processo em vez de embutir um caminho relativo,
    # para o teste não depender de onde o pytest foi chamado nem do layout.
    saidas = set()
    for seed in ("0", "1", "42", "12345"):
        env = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": os.pathsep.join(p for p in sys.path if p),
        }
        resultado = subprocess.run(
            [sys.executable, "-c", script],
            env=env, capture_output=True, text=True, check=True,
        )
        saidas.add(resultado.stdout.strip())
    assert len(saidas) == 1, f"numeracao instavel entre processos: {saidas}"


# --------------------------------------------------------------------------
# Caminho LLM (sem rede: a resposta do ollama é substituída por um stub)
# --------------------------------------------------------------------------
def _resposta_falsa(payload):
    """Imita o ChatResponse do ollama: o conteúdo fica em message.content."""
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))


def test_llm_descarta_valor_que_nao_existe_no_texto(anon_ptbr, monkeypatch):
    """Valor alucinado/parafraseado viraria um re.sub inócuo, fingindo anonimizar."""
    texto = "Meu nome é Maria e moro em Vitoria."
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"anon_model_output": [
            {"tipo": "PERSON_NAME", "valor": "Maria"},
            {"tipo": "PERSON_NAME", "valor": "Mariazinha"},   # não está no texto
            {"tipo": "LOCATION", "valor": "Vitoria"},
        ]}),
    )
    entidades = anon_ptbr.find_undeterministic_entities(texto)
    assert entidades == {"PERSON_NAME": {"Maria"}, "LOCATION": {"Vitoria"}}


def test_llm_preserva_duas_entidades_do_mesmo_tipo(anon_ptbr, monkeypatch):
    """O motivo de a saída ser lista, e não dict: dict perderia um dos nomes."""
    texto = "Maria é filha de Joshua Smith."
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"anon_model_output": [
            {"tipo": "PERSON_NAME", "valor": "Maria"},
            {"tipo": "PERSON_NAME", "valor": "Joshua Smith"},
        ]}),
    )
    saida = mascarar(anon_ptbr, texto, use_llm=True)
    assert saida == "[PERSON_NAME_1] é filha de [PERSON_NAME_0]."


def test_regex_tem_prioridade_sobre_o_llm(anon_ptbr, monkeypatch):
    """Se os dois acharem o mesmo valor, ele não pode receber duas tags."""
    texto = "O CPF 123.345.123-45 é da Maria."
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"anon_model_output": [
            {"tipo": "PERSON_NAME", "valor": "Maria"},
            {"tipo": "MONEY", "valor": "123.345.123-45"},   # o regex já pegou
        ]}),
    )
    saida = mascarar(anon_ptbr, texto, use_llm=True)
    assert saida == "O CPF [CPF_0] é da [PERSON_NAME_0]."
    assert "MONEY" not in saida


def test_llm_nao_duplica_tag_de_valor_sobreposto_ao_regex(anon_ptbr, monkeypatch):
    """O LLM devolve o telefone com o "+"; o regex capturou sem ele.

    As strings diferem, então a deduplicação por igualdade deixava passar e o
    mesmo telefone acabava com duas tags, uma delas órfã (no dict, fora do texto).
    """
    texto = "Meu celular é +2799778-5677."
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"anon_model_output": [
            {"tipo": "PERSON_NAME", "valor": "+2799778-5677"},
        ]}),
    )
    masked, tags = anon_ptbr.anonimize_text(texto, use_llm=True)
    assert list(tags) == ["[TELEFONE_BR_0]"]
    assert "PERSON_NAME" not in masked


def test_tags_devolvidas_existem_todas_no_texto(anon_ptbr, monkeypatch):
    """Tag órfã no mapa inviabiliza desanonimizar depois."""
    texto = "CNH: 12345678901 e Maria."
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"anon_model_output": [
            {"tipo": "PERSON_NAME", "valor": "Maria"},
        ]}),
    )
    masked, tags = anon_ptbr.anonimize_text(texto, use_llm=True)
    assert all(tag in masked for tag in tags), f"tags fora do texto: {tags}"


def test_llm_rejeita_json_fora_do_schema(anon_ptbr, monkeypatch):
    monkeypatch.setattr(
        anon_ptbr, "get_llm_response",
        lambda prompt, format_schema=None: _resposta_falsa({"resposta": "qualquer coisa"}),
    )
    with pytest.raises(ValueError, match="não bate com o schema"):
        anon_ptbr.find_undeterministic_entities("Maria")


def test_anonimize_text_sem_llm_nao_toca_a_rede(anon_ptbr, monkeypatch):
    """use_llm=False é o default: a suíte inteira roda sem servidor."""
    def explode(*args, **kwargs):
        raise AssertionError("get_llm_response nao deveria ser chamado")

    monkeypatch.setattr(anon_ptbr, "get_llm_response", explode)
    assert mascarar(anon_ptbr, "CPF 123.345.123-45") == "CPF [CPF_0]"


# --------------------------------------------------------------------------
# Regressão de PROMPT — chamadas reais ao Ollama.
#
# Ficam fora da suíte padrão (pytest.ini desmarca "llm") porque dependem de
# servidor e de um modelo, e porque a saída de um LLM não é garantida nem com
# temperature=0. Rode-os de propósito ao mexer no prompt:
#
#     python3 -m pytest -m llm
#
# Stub não serviria aqui: o que se quer verificar é justamente se as regras do
# prompt continuam surtindo efeito no modelo.
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def anon_llm():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(_SRC), "config", ".env"))
    modelo = os.getenv("LLM_MODEL_NAME")
    anon = Anonymizer(**({"llm_model_name": modelo} if modelo else {}))
    try:
        anon._llm_client.show(anon.llm_model_name)
    except Exception as e:
        pytest.skip(f"Ollama indisponivel ou modelo ausente: {e}")
    return anon


@pytest.mark.llm
def test_llm_captura_pessoa_citada_por_vinculo_familiar(anon_llm):
    """Regra do prompt: terceiros mencionados por vínculo ('filha de X').

    Antes da regra, o modelo devolvia só a pessoa que fala e o Joshua Smith
    passava batido — ou vinha rotulado como ORGANIZATION.
    """
    texto = "Ele tinha 35 anos, sou filha de Joshua Smith e meu CPF é 111.222.333-44."
    masked, tags = anon_llm.anonimize_text(texto, use_llm=True)
    assert "Joshua Smith" not in masked
    assert "Joshua Smith" in tags.values()


@pytest.mark.llm
def test_llm_captura_idade_como_age(anon_llm):
    """Regra do prompt: '<numero> anos' é AGE.

    Sem AGE na lista de entidades, '35 anos' caía em DATE.
    """
    masked, tags = anon_llm.anonimize_text("Ele tinha 35 anos.", use_llm=True)
    assert "35 anos" not in masked
    assert any(tag.startswith("[AGE_") for tag in tags), tags


@pytest.mark.llm
def test_llm_captura_nome_solto_sem_vinculo(anon_llm):
    """Contraprova da regra de vínculo: nome sem parentesco declarado.

    A regra fala em 'pai de', 'filha de'; era preciso confirmar que ela não
    estreitou o modelo a ponto de ignorar um nome solto.
    """
    texto = "Meu cpf é 123.345.123-45, o Carlos é amigo de todos."
    masked, tags = anon_llm.anonimize_text(texto, use_llm=True)
    assert "Carlos" not in masked
    assert "Carlos" in tags.values()



if __name__ == "__main__":
    # Sem isto, rodar o arquivo direto apenas definiria as funções e sairia sem
    # executar nada: fixtures e parametrize só têm efeito sob o pytest.
    raise SystemExit(pytest.main([__file__, "-v"]))
