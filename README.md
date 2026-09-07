# Sentence-anonimizer

Detects and masks personally identifiable information (PII) in free text, replacing
each value with a stable tag and returning the tag → original value mapping.

Supports Brazilian Portuguese (`pt-br`) and English (`en`).

## How it works

Two layers, and the split matters:

| Layer | Finds | Guarantees |
| --- | --- | --- |
| **Regex** (always on) | Formatted data: CPF, CNPJ, e-mail, phone, credit card, CEP… | Deterministic. Same input, same output, no network. |
| **LLM via Ollama** (opt-in) | Context-dependent data regex cannot express: names, places, organizations | Best effort. Recall varies between runs. |

The LLM only **identifies** entities and returns them as structured JSON. The masking
itself is always done in code, reusing the same tagging machinery as the regex layer.
The model never rewrites your text, so it cannot silently drop or alter passages.

## Install

```bash
pip install anon-lib            # regex layer only
pip install "anon-lib[llm]"     # adds the optional LLM layer
```

The base install has a single dependency and never touches the network. `ollama` and
`pydantic` come only with the `llm` extra and are imported lazily, so calling
`use_llm=True` without them raises an actionable `ImportError` instead of a bare
`ModuleNotFoundError`.

The LLM layer also needs a running [Ollama](https://ollama.com) server with a model
pulled:

```bash
ollama pull qwen3:0.6b
```

Point the library at it with the `llm_model_name` argument, or read it from your own
config:

```python
Anonymizer(llm_model_name="qwen3:0.6b")
```

## Usage

`anonimize_text` returns a `(masked_text, tags)` tuple. Every tag in the mapping is
guaranteed to appear in the masked text.

### Regex only (default)

```python
from anon_lib import Anonymizer

anon = Anonymizer(language="pt-br")
masked, tags = anon.anonimize_text(
    "Contato: joao.silva@empresa.com.br, CPF 123.456.789-00, "
    "CNPJ 12.345.678/0001-99, cel (11) 98765-4321."
)
```

```
Contato: [EMAIL_0], CPF [CPF_0], CNPJ [CNPJ_NUMERICO_FORMATADO_0], cel [TELEFONE_BR_0].

{'[EMAIL_0]': 'joao.silva@empresa.com.br',
 '[CPF_0]': '123.456.789-00',
 '[CNPJ_NUMERICO_FORMATADO_0]': '12.345.678/0001-99',
 '[TELEFONE_BR_0]': '(11) 98765-4321'}
```

### Regex + LLM

```python
masked, tags = anon.anonimize_text(
    "Meu nome é Maria, moro na Rua das Flores, 123 e meu CPF é 111.222.333-44.",
    use_llm=True,
)
```

```
Meu nome é [PERSON_NAME_0], moro na [LOCATION_0], 123 e meu CPF é [CPF_0].

{'[CPF_0]': '111.222.333-44',
 '[PERSON_NAME_0]': 'Maria',
 '[LOCATION_0]': 'Rua das Flores'}
```

Note the house number `123` left unmasked: that is real output, and it illustrates why
the regex layer is the one you rely on for guarantees.

Run both layers end to end with `python examples/demo.py`.

## Detected patterns

**pt-br** — `CPF`, `CNPJ_NUMERICO_FORMATADO`, `CNPJ_ALFANUMERICO`, `CNPJ_NUMERICO`,
`CNPJ_ALFANUMERICO_SEM_PONTUACAO`, `RG`, `PIS_PASEP`, `TITULO_ELEITOR`, `CNH`, `EMAIL`,
`TELEFONE_BR`, `CEP`, `DATA`, `PLACA_VEICULO`, `PLACA_VEICULO_MERCOSUL`,
`CARTAO_CREDITO`, `CARTAO_CREDITO_AMEX`, `CHAVE_PIX_ALEATORIA`, `AGENCIA`,
`CONTA_BANCARIA`, `IP`

**en** — `EMAIL`, `SSN`, `CREDIT_CARD`, `CREDIT_CARD_AMEX`, `US_PHONE`, `US_ZIP`, `IP`

**LLM entity types** — `PERSON_NAME`, `LOCATION`, `ORGANIZATION`, `DATE`, `AGE`,
`TIME`, `MONEY`, `PERCENT`, `FACILITY`, `GPE` (configurable via
`list_of_undeterministics_entities`; the list is injected into the response schema as an
enum, so the model cannot return a type outside it).

## Design notes

**Declaration order is priority.** Some values match several patterns — 11 bare digits
are both a CPF and a mobile number. The first pattern declared wins, so formatted
patterns come first and ambiguous bare numerics last.

**Longest value is replaced first.** The leading 12 digits of a spaced credit card also
match a voter ID. Replacing the shorter value first would corrupt the longer one.

**Label-anchored patterns include the label.** `CNH`, `AGENCIA` and `CONTA_BANCARIA` mask
the label too (`CNH: 12345678901` → `[CNH_0]`), because the bare number is
indistinguishable from a CPF without it.

**LLM values absent from the text are discarded.** A paraphrased or invented value would
produce a no-op substitution while making the output *look* anonymized.

## Known limitations

- **No check-digit validation.** A well-formed but arithmetically invalid CPF is still
  masked. For anonymization, over-detection is the safe side.
- **`DATA` matches any `dd/mm/aaaa` date**, with no way to tell a birth date from any
  other. Distinguishing them requires context, which is the LLM layer's job.
- **`US_ZIP` matches any 5-digit number**, and bare 11-digit runs are inherently
  ambiguous between CPF, CNH and mobile numbers.
- **`MONEY`, `PERCENT` and `TIME` are not PII** and only add noise. Adjust
  `list_of_undeterministics_entities` for your use case — the list is injected into the
  response schema as an enum, so it is the effective control over what the model may
  return.
- **Tag numbering may skip an index.** When a short value is also a substring of a longer
  masked one, it stays registered to catch standalone occurrences elsewhere. Dropping it
  would leak PII.

## Tests

```bash
pip install -e ".[dev]"   # needs Python 3.9+, as declared in pyproject.toml
pytest        # 53 tests, hermetic: no server, no network (~2s)
pytest -m llm # 3 prompt-regression tests against a real Ollama
```

The default suite stubs every LLM response, so it needs no server. The `llm` marker is
deselected by default and holds the tests that call the model for real — they verify the
prompt rules still take effect, which a stub cannot do, and skip themselves when Ollama
or the model is unavailable.

## Layout

```text
src/anon_lib/__init__.py                 public API: Anonymizer, __version__
src/anon_lib/anonymizer.py               Anonymizer
src/anon_lib/patterns/patterns.py        regex pattern tables, per language
src/anon_lib/schemas/models_schemas.py   AnonOutput / PIIEntity (LLM response schema)
examples/demo.py                         runnable demo of both layers
tests/test_anonymizer.py                 test suite
```
