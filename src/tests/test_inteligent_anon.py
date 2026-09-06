import os
import subprocess
import sys
import pytest

# Sob o pytest, o diretório "src" entra no sys.path via `pythonpath` no pytest.ini.
# Este bloco cobre a execução direta (python3 src/tests/test_inteligent_anon.py),
# em que o sys.path[0] é "src/tests" e o import falharia.
# O caminho é absoluto e derivado do __file__ de propósito: um relativo como "../"
# seria resolvido contra o diretório de onde o comando foi chamado, não contra
# este arquivo. E o insert(0) é necessário para que "scripts" resolva neste
# projeto, e não no pacote homônimo instalado em site-packages.
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scripts.models.inteligent_anon import IntelligentAnonnimizer

@pytest.fixture(scope="module")
def anon_ptbr():
    return IntelligentAnonnimizer(language="pt-br")


@pytest.fixture(scope="module")
def anon_en():
    return IntelligentAnonnimizer(language="en")


# --------------------------------------------------------------------------
# Um caso por padrão declarado em pt-br
# --------------------------------------------------------------------------
CASOS_PTBR = [
    ("Contato: joao.silva@empresa.com.br", "Contato: <EMAIL_0>"),
    ("Pix: 550e8400-e29b-41d4-a716-446655440000", "Pix: <CHAVE_PIX_ALEATORIA_0>"),
    ("CPF 123.345.123-45", "CPF <CPF_0>"),
    ("CNPJ 12.345.678/0001-99", "CNPJ <CNPJ_NUMERICO_FORMATADO_0>"),
    ("CNPJ 12.ABC.345/01DE-35", "CNPJ <CNPJ_ALFANUMERICO_0>"),
    ("RG 12.345.678-9", "RG <RG_0>"),
    ("PIS 123.45678.90-1", "PIS <PIS_PASEP_0>"),
    ("CEP 01310-100", "CEP <CEP_0>"),
    ("Nasceu em 05/09/1990", "Nasceu em <DATA_NASCIMENTO_0>"),
    ("Placa ABC1D23", "Placa <PLACA_VEICULO_MERCOSUL_0>"),
    ("Placa ABC-1234", "Placa <PLACA_VEICULO_0>"),
    ("Cartao 4111 1111 1111 1111", "Cartao <CARTAO_CREDITO_0>"),
    ("Amex 3782 822463 10005", "Amex <CARTAO_CREDITO_AMEX_0>"),
    ("Servidor 192.168.0.14", "Servidor <IP_0>"),
    ("Ligue (11) 98765-4321", "Ligue <TELEFONE_BR_0>"),
    ("Ligue +55 11 98765-4321", "Ligue <TELEFONE_BR_0>"),
    ("Ligue 1134567890", "Ligue <TELEFONE_BR_0>"),
    ("Titulo 1234 5678 9012", "Titulo <TITULO_ELEITOR_0>"),
    ("CNPJ 12345678000199", "CNPJ <CNPJ_NUMERICO_0>"),
    ("CPF 12345678901", "CPF <CPF_0>"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_PTBR)
def test_padroes_ptbr(anon_ptbr, texto, esperado):
    assert anon_ptbr.anonimize_text(texto) == esperado


CASOS_EN = [
    ("Email me at jane.doe@example.com", "Email me at <EMAIL_0>"),
    ("SSN 123-45-6789", "SSN <SSN_0>"),
    ("Card 4111-1111-1111-1111", "Card <CREDIT_CARD_0>"),
    ("Amex 3782 822463 10005", "Amex <CREDIT_CARD_AMEX_0>"),
    ("Server 192.168.0.14", "Server <IP_0>"),
    ("ZIP 90210", "ZIP <US_ZIP_0>"),
    ("ZIP 90210-1234", "ZIP <US_ZIP_0>"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_EN)
def test_padroes_en(anon_en, texto, esperado):
    assert anon_en.anonimize_text(texto) == esperado


def test_telefone_en_preserva_pontuacao_de_abertura(anon_en):
    """O \\b inicial fazia o '(' e o '+' ficarem de fora do match."""
    assert anon_en.anonimize_text("Call (415) 555-2671 now") == "Call <US_PHONE_0> now"
    assert anon_en.anonimize_text("Call +1-415-555-2671 now") == "Call <US_PHONE_0> now"


# --------------------------------------------------------------------------
# Padrões ancorados por rótulo: o rótulo entra no trecho mascarado
# --------------------------------------------------------------------------
CASOS_COM_ROTULO = [
    ("CNH: 12345678901", "<CNH_0>"),
    ("Agencia 0001-2", "<AGENCIA_0>"),
    ("conta 123456-7", "<CONTA_BANCARIA_0>"),
]


@pytest.mark.parametrize("texto,esperado", CASOS_COM_ROTULO)
def test_padroes_ancorados_por_rotulo(anon_ptbr, texto, esperado):
    assert anon_ptbr.anonimize_text(texto) == esperado


# --------------------------------------------------------------------------
# Resolução de conflito entre padrões
# --------------------------------------------------------------------------
def test_cartao_vence_titulo_de_eleitor(anon_ptbr):
    """Os 12 primeiros dígitos de um cartão espaçado casam com TITULO_ELEITOR.

    Se o valor curto fosse substituído primeiro, o cartão seria corrompido.
    """
    saida = anon_ptbr.anonimize_text("Cartao 1234 5678 9012 3456 pago hoje")
    assert saida == "Cartao <CARTAO_CREDITO_0> pago hoje"


def test_cnpj_numerico_tem_prioridade_sobre_alfanumerico(anon_ptbr):
    """[A-Z0-9] também casa dígitos: o padrão numérico precisa vir antes."""
    assert "<CNPJ_NUMERICO_FORMATADO_0>" in anon_ptbr.anonimize_text("12.345.678/0001-99")
    assert "<CNPJ_NUMERICO_0>" in anon_ptbr.anonimize_text("12345678000199")


def test_sem_chaves_duplicadas_no_dicionario_de_padroes():
    """Chave repetida num dict literal é sobrescrita em silêncio.

    Não dá para detectar em runtime: o Python já descartou a duplicata na análise
    sintática. Por isso lemos a AST do fonte. Este bug já apagou padrões duas
    vezes (as 4 chaves "CNPJ", depois um segundo "CPF" que matou o formatado).
    """
    import ast

    from scripts.models import inteligent_anon

    with open(inteligent_anon.__file__, encoding="utf-8") as arquivo:
        arvore = ast.parse(arquivo.read())

    duplicadas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Dict):
            continue
        chaves = [
            k.value for k in no.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        duplicadas += sorted({c for c in chaves if chaves.count(c) > 1})

    assert duplicadas == [], f"chaves duplicadas apagam padroes: {duplicadas}"


def test_cpf_cobre_as_duas_formas_com_a_mesma_tag(anon_ptbr):
    assert anon_ptbr.anonimize_text("CPF 123.456.789-00") == "CPF <CPF_0>"
    assert anon_ptbr.anonimize_text("CPF 12345678901") == "CPF <CPF_0>"


def test_telefone_tem_prioridade_sobre_cpf_sem_pontuacao(anon_ptbr):
    """11 dígitos crus são ambíguos; o padrão de celular é o mais específico."""
    assert anon_ptbr.anonimize_text("Ligue 11987654321") == "Ligue <TELEFONE_BR_0>"


def test_dotted_quad_invalido_como_ip_cai_em_cpf(anon_ptbr):
    """345 > 255, então não é IP; o CPF com separador tolerante pega."""
    assert anon_ptbr.anonimize_text("Doc 123.345.123.45") == "Doc <CPF_0>"


def test_valor_curto_contido_em_valor_longo_nao_vaza_isolado(anon_ptbr):
    """O número da CNH rotulada também aparece solto: as duas ocorrências somem."""
    saida = anon_ptbr.anonimize_text("CNH: 12345678901 e de novo 12345678901 aqui")
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
        if alvo in anon_ptbr.anonimize_text(texto):
            vazamentos.append(n)
    assert vazamentos == []


# --------------------------------------------------------------------------
# Comportamento geral
# --------------------------------------------------------------------------
def test_texto_sem_pii_fica_intacto(anon_ptbr):
    texto = "Reuniao marcada para a sala 3 do predio azul."
    assert anon_ptbr.anonimize_text(texto) == texto


def test_multiplos_valores_do_mesmo_tipo_recebem_tags_distintas(anon_ptbr):
    saida = anon_ptbr.anonimize_text("CPF 111.222.333-44 e CPF 555.666.777-88")
    assert saida == "CPF <CPF_0> e CPF <CPF_1>"


def test_idioma_nao_suportado(anon_ptbr):
    anon = IntelligentAnonnimizer(language="fr")
    with pytest.raises(ValueError, match="não suportado"):
        anon.anonimize_text("texto qualquer")


@pytest.mark.parametrize("entrada", [None, []])
def test_find_keywords_sem_conteudo(anon_ptbr, entrada):
    with pytest.raises(ValueError, match="Sem sentença"):
        anon_ptbr.find_keywords_and_replace(chunks_of_sentence_text=entrada)


def test_numeracao_de_tags_estavel_entre_processos():
    """Iterar um set de strings varia com o PYTHONHASHSEED; sorted() estabiliza."""
    script = (
        "from scripts.models.inteligent_anon import IntelligentAnonnimizer;"
        "print(IntelligentAnonnimizer(language='pt-br').anonimize_text("
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


if __name__ == "__main__":
    # Sem isto, rodar o arquivo direto apenas definiria as funções e sairia sem
    # executar nada: fixtures e parametrize só têm efeito sob o pytest.
    raise SystemExit(pytest.main([__file__, "-v"]))
