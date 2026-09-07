"""Demonstracao das duas camadas do anon-lib.

    python examples/demo.py

A camada LLM precisa de um Ollama no ar e do extra: pip install anon-lib[llm]
"""
import os
import sys

# Com o pacote instalado (pip install anon-lib) o import abaixo ja funciona.
# Este bloco cobre o uso direto do repositorio, sem instalar.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_RAIZ, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from anon_lib import Anonymizer

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_RAIZ, "config", ".env"))
except ImportError:
    pass

if __name__ == "__main__":
    modelo = os.getenv("LLM_MODEL_NAME")
    anon = Anonymizer(**({"llm_model_name": modelo} if modelo else {}))

    # 1) Camada regex: deterministica e sem rede.
    texto = ("Meu cpf é 123.345.123-45, o Carlos é amigo de todos, mas isso não muda "
             "meu celular +2799778-5677 e o cpf ser 123.345.123-45")
    mascarado, tags = anon.anonimize_text(sentence_text=texto)
    print("== regex ==")
    print(mascarado)
    print(tags)

    # 2) Regex + LLM: o LLM so acrescenta o que o regex nao alcanca.
    texto2 = ("José Carlos foi assaltado no dia 20/12/2023, tinha 35 anos e é filho de "
              "Joshua Smith. Mora na Rua das Flores, 123, CPF 111.222.333-44.")
    print("\n== regex + llm ==")
    try:
        mascarado2, tags2 = anon.anonimize_text(sentence_text=texto2, use_llm=True)
        print(mascarado2)
        print(tags2)
    except (ImportError, ValueError) as e:
        print(f"camada LLM indisponivel ({e}); so regex:")
        print(anon.anonimize_text(sentence_text=texto2)[0])
