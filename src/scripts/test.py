import sys
sys.path.append("../")
from models.inteligent_anon import IntelligentAnonnimizer
import os 
from dotenv import load_dotenv

load_dotenv("./config/.env")

if __name__=="__main__":
    anon=IntelligentAnonnimizer()
    # Sentença de teste
    teste="Meu cpf é 123.345.123-45, o Carlos é amigo de todos, mas isso não muda meu celular +2799778-5677 e o cpf ser 123.345.123-45"
    mascarado=anon.anonimize_text(sentence_text=teste)
    print(f"{mascarado}")
    # Teste de múltiplos valores do mesmo tipo com o OLLAMA
    teste2="CPF 111.222.333-44 e CPF 555.666.777-88"
    mascarado2=anon.get_llm_response_text(text=teste2)
    print(f"{mascarado2}")