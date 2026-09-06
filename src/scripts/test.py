import os
import sys
from dotenv import load_dotenv
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RAIZ = os.path.dirname(_SRC)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

load_dotenv(os.path.join(_RAIZ, "config", ".env"))

from scripts.models.inteligent_anon import IntelligentAnonnimizer

if __name__ == "__main__":
    modelo = os.getenv("LLM_MODEL_NAME")
    anon = IntelligentAnonnimizer(**({"llm_model_name": modelo} if modelo else {}))

    # 1) Caminho regex: determinístico e sem rede.
    teste = ("Meu cpf é 123.345.123-45, o Carlos é amigo de todos, mas isso não muda "
             "meu celular +2799778-5677 e o cpf ser 123.345.123-45")
    print("== regex ==")
    print(anon.anonimize_text(sentence_text=teste))

    # 2) Regex + LLM: o LLM só acrescenta o que o regex não alcança (nome, idade).
    teste2 = ("Meu nome é Maria, tenho 35 anos, sou filha de Joshua Smith "
              "e meu CPF é 111.222.333-44. Moro na Rua das Flores, 123, e meu celular é +2799778-5677.")
    print("\n== regex + llm ==")
    try:
        masked_text, dict_unique_tags = anon.anonimize_text(sentence_text=teste2, use_llm=True)
        print(f"Texto anonimizado: {masked_text}")
        print(f"Tags únicas: {dict_unique_tags}")
    except ValueError as e:
        print(f"LLM indisponivel ({e}); rodando so com regex:")
        print(anon.anonimize_text(sentence_text=teste2))
