import os
import json
import random
import re
import ollama
from dotenv import load_dotenv
from faker import Faker
from tqdm import tqdm


load_dotenv("./config/.env")


# ============================================================
# Configuração
# ============================================================

LLM_IPADDRESS_SERVICE = "http://localhost:11434"

LLM_MODEL_NAME = os.getenv(
    "LLM_MODEL_NAME",
    "qwen3.5:4b"
)

OUTPUT_DIR = "./data/results"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "dados.jsonl"
)

# ============================================================
# Validação do template
# ============================================================
PLACEHOLDERS = [
    "[PERSON_NAME]",
    "[EMAIL]",
    "[ADDRESS]",
    "[DATE]",
    "[LOCATION]",
    "[CREDIT_CARD]",
    "[DOCUMENT_ID]",
    "[PHONE]",
    "[COMPANY]",
    "[IP_ADDRESS]",
]

_llm_client = ollama.Client(
    host=LLM_IPADDRESS_SERVICE
)

# Tags de raciocínio: se aparecerem, o modelo pensou.
_THINK_BLOCK = re.compile(
    r"</?(think|thinking)\b",
    re.IGNORECASE
)


# ============================================================
# LLM
# ============================================================
def get_llm_response(
    prompt: str,
    temperature: float = 0.1,
    think: bool=False
):
    if not prompt:
        raise ValueError("Prompt vazio!")

    response = _llm_client.chat(
        model=LLM_MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        think=think,
        options={
            "temperature": temperature,
            "enable_thinking": think
        },
    )

    mensagem = response["message"]

    raciocinio = mensagem.get("thinking")

    conteudo = mensagem["content"]

    if raciocinio or _THINK_BLOCK.search(conteudo):
        raise RuntimeError(
            "O modelo gerou raciocínio interno mesmo "
            "com think=False. Use um modelo sem "
            "thinking ou uma versão do Ollama que "
            "respeite o parâmetro."
        )

    return conteudo.strip()

def gerar_valores():
    """
    Faker gera os valores.
    Estes valores são a ground truth.
    """

    locale = random.choice([
        "pt_BR",
        "en_US",
        "fr_FR"
    ])

    fake = Faker(locale)

    list_of_items = {
        "PERSON_NAME": fake.name(),
        "EMAIL": fake.email(),
        "ADDRESS": fake.address().replace("\n"," "),
        "DATE": fake.date_of_birth().strftime("%d/%m/%Y"),
        "LOCATION": fake.city(),
        "CREDIT_CARD": fake.credit_card_number(),
        "PHONE": fake.phone_number(),
        "COMPANY": fake.company(),
        "IP_ADDRESS": fake.ipv4(),
    }

    if locale=="pt_BR":
        list_of_items.update({"DOCUMENT_ID": fake.cpf()})
    elif locale=="en_US":
        list_of_items.update({"DOCUMENT_ID": fake.passport_number()})
    elif locale=="fr_FR":
        list_of_items.update({"DOCUMENT_ID": fake.ssn()})

    return list_of_items

def generate_sentence_template():
    """
    Apenas cria uma frase usando marcadores.
    """
    prompt = """
    /set nothink

Gere UMA única frase natural, realista e gramatical
em contexto cotidiano, administrativo, médico, jornalístico, técnico. pesquisa-científica ou jurídico.

A frase deve utilizar TODOS os marcadores abaixo
exatamente uma vez:

[PERSON_NAME]
[EMAIL]
[ADDRESS]
[DATE]
[LOCATION]
[CREDIT_CARD]
[DOCUMENT_ID]
[PHONE]
[COMPANY]
[IP_ADDRESS]

Regras obrigatórias:

1. Responda somente com a frase.
2. Não explique nada.
3. Não crie valores para os marcadores.
4. Não remova nenhum marcador.
5. Não altere os marcadores.
6. Cada marcador deve aparecer exatamente uma vez.
7. A frase deve ser natural.
8. Os marcadores devem estar integrados à frase.

Exemplo válido:

Em [DATE], [PERSON_NAME] confirmou seu cadastro pelo e-mail
[EMAIL] e informou residência em [LOCATION], no endereço
[ADDRESS].


IMPORTANTE: Você DEVE responder SEM usar raciocínio interno.
Não use tags <think></think>.
Não mencione "deixe-me pensar" ou similar.
Responda DIRETO e SEM DEMORA.

"""

    return get_llm_response(
        prompt,
        temperature=0.3
    )

def verificar_template(template: str):
    """
    Verifica se o LLM respeitou os marcadores.
    """

    if not template:
        return False

    # Todos devem existir
    for placeholder in PLACEHOLDERS:
        if placeholder not in template:
            return False

    # Cada marcador deve aparecer exatamente uma vez
    for placeholder in PLACEHOLDERS:
        if template.count(placeholder) != 1:
            return False

    return True

def preencher_template(
    template: str,
    valores: dict
):
    """
    Substitui os placeholders pelos valores reais.

    Nenhum LLM participa desta etapa.
    """

    frase = template

    for entidade, valor in valores.items():

        placeholder = f"[{entidade}]"

        frase = frase.replace(
            placeholder,
            valor
        )

    return frase

def verificar(
    frase: str,
    valores: dict
):
    """
    Verificação determinística.

    Todos os valores devem aparecer literalmente.
    """

    return all(
        valor in frase
        for valor in valores.values()
    )

def salvar_jsonl(
    registros: list,
    output_file: str
):
    if not registros:
        return

    os.makedirs(
        os.path.dirname(output_file),
        exist_ok=True
    )

    with open(
        output_file,
        "a",
        encoding="utf-8"
    ) as f:

        for registro in registros:

            f.write(
                json.dumps(
                    registro,
                    ensure_ascii=False
                ) + "\n"
            )

if __name__ == "__main__":
    n = 500

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    validas = 0
    tentativas = 0
    registros = []

    with tqdm(total=n, desc="Gerando amostras", unit="amostra") as pbar:
        while validas < n:
            tentativas += 1
            valores = gerar_valores()            

            try:
                template = generate_sentence_template()
                print(f"\nTemplate:\n{template}\n")

                if not verificar_template(template):
                    print(
                        "Template inválido. Descartando..."
                    )
                    continue

                frase = preencher_template(template, valores)
                print(f"Frase:\n{frase}\n")

                if not verificar(frase, valores):
                    print("ERRO: entidade não encontrada.")
                    continue

                registros.append({
                    "text": frase,
                    "entities": valores
                })

                validas += 1
                pbar.update(1)

                if len(registros) >= 10:
                    salvar_jsonl(
                        registros,
                        OUTPUT_FILE
                    )
                    registros = []

                pbar.set_postfix(
                    validas=validas,
                    tentativas=tentativas,
                    taxa=f"{validas / tentativas * 100:.1f}%"
                )

            except Exception as e:
                print(f"\nErro ao processar amostra: {e}")

        salvar_jsonl(registros, OUTPUT_FILE)

    print("\nProcessamento concluído.")
    print(f"Amostras solicitadas: {n}")
    print(f"Amostras válidas: {validas}")
    print(f"Tentativas: {tentativas}")
    print(
        f"Taxa de sucesso: "
        f"{validas / tentativas * 100:.2f}%"
    )
    print(f"Arquivo: {OUTPUT_FILE}")