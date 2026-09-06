import sys
sys.path.append("../")
from models.inteligent_anon import IntelligentAnonnimizer


if __name__=="__main__":
    anon=IntelligentAnonnimizer()
    # Sentença de teste
    teste="Meu cpf é 123.345.123-45, o Carlos é amigo de todos, mas isso não muda meu celular +2799778-5677 e o cpf ser 123.345.123-45"
    mascarado=anon.anonimize_text(sentence_text=teste)
    print(f"{mascarado}")