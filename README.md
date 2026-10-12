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
Meu nome é [PERSON_NAME_0], moro na [ADDRESS_0] e meu CPF é [CPF_0].

{'[PERSON_NAME_0]': 'Maria',
 '[ADDRESS_0]': 'Rua das Flores, 123',
 '[CPF_0]': '111.222.333-44'}
```

Names and addresses are deliberately **not** regex patterns: they are not deterministic,
so they belong to the LLM layer. The output above comes from a small model (`qwen3:0.6b`)
and will vary with the model; the regex layer is the one you rely on for guarantees.

Run both layers end to end with `python examples/demo.py`.

### Inspect before masking: `analyze()`

`analyze` returns the entities with their position and a confidence score, without
touching the text:

```python
for e in anon.analyze("Mail joao@x.com, CPF 111.222.333-44"):
    print(e)
```

```
RecognizedEntity(type='EMAIL', value='joao@x.com', start=5, end=15, score=1.0)
RecognizedEntity(type='CPF', value='111.222.333-44', start=21, end=35, score=0.5)
```

`text[e.start:e.end] == e.value` always holds, and every occurrence of a value is
reported. Entities are sorted by position. `analyze(text, use_llm=True)` merges the LLM
entities; where regex and LLM overlap, the regex wins.

| Score | Meaning |
| --- | --- |
| `1.0` | Regex match (with a valid check digit, for types that have one) |
| `0.5` | Regex match whose check digit is invalid (only when `strict=False`) |
| `0.8` | LLM entity (fixed: Ollama does not expose per-entity confidence) |

`min_score` filters by score, in both `analyze` and `anonimize_text`:

```python
anon.anonimize_text(text, min_score=0.9)   # leaves invalid-check-digit CPFs alone
```

### Check-digit validation: `strict=True`

By default every well-formed match is masked, which is the safe side for anonymization.
With `strict=True`, CPF, CNPJ (numeric and alphanumeric) and credit cards (Luhn) with an
invalid check digit are discarded, which cuts false positives:

```python
Anonymizer(strict=True).anonimize_text("CPF 111.222.333-44 e 529.982.247-25")
# ('CPF 111.222.333-44 e [CPF_0]', {'[CPF_0]': '529.982.247-25'})
```

A rejected span also blocks lower-priority patterns from masking a piece of it (an
invalid card number is not re-read as a voter ID). The trade-off: a real CPF typed with
a mistake is no longer masked, so keep `strict=False` if a leak is worse than a false
positive. The validators are also importable from `anon_lib.validators`.

### Stable tags: `tag_style="hash"`

The default `[CPF_0]` is positional: the index depends on the other values in the text,
so the same CPF can get different tags in different texts. `tag_style="hash"` derives
the tag from the value instead:

```python
Anonymizer(tag_style="hash").anonimize_text("CPF 529.982.247-25")
# ('CPF [CPF_e0897535]', {'[CPF_e0897535]': '529.982.247-25'})
```

The same value gets the same tag in any text and any process, so documents can be
correlated. The hash is an unkeyed SHA-256 prefix: for small value spaces (a CPF has
about 10⁹ possibilities) it can be brute-forced, so treat the tag mapping as sensitive
if the masked text leaves your organization.

## Detected patterns

**pt-br** — `CPF`, `CNPJ_NUMERICO_FORMATADO`, `CNPJ_ALFANUMERICO`, `CNPJ_NUMERICO`,
`CNPJ_ALFANUMERICO_SEM_PONTUACAO`, `RG`, `PIS_PASEP`, `TITULO_ELEITOR`, `CNH`, `EMAIL`,
`TELEFONE_BR`, `CEP`, `DATA`, `PLACA_VEICULO`, `PLACA_VEICULO_MERCOSUL`,
`CARTAO_CREDITO`, `CARTAO_CREDITO_AMEX`, `CHAVE_PIX_ALEATORIA`, `AGENCIA`,
`CONTA_BANCARIA`, `IP`

**Deny-list** — your own sensitive terms, checked before the regex layer:

```python
anon = Anonymizer(language="en", deny_list=["Project Aurora"])               # type DENY_LIST
anon = Anonymizer(language="en", deny_list={"CODENAME": ["Aurora", "Zeus"]}, # custom type
                  deny_list_ignore_case=False)                               # default: True
```

**fr** — `EMAIL`, `IBAN_FR`, `NIR`, `SIRET`, `SIREN`, `CARTE_BANCAIRE`, `CARTE_BANCAIRE_AMEX`, `IP`, `DATE`, `CARTE_IDENTITE`, `TELEPHONE_FR`, `CODE_POSTAL` (IBAN, NIR, SIRET, SIREN and cards are checksum-validated)

**en** — `EMAIL`, `SSN`, `CREDIT_CARD`, `CREDIT_CARD_AMEX`, `US_PHONE`, `US_ZIP`, `IP`

**LLM entity types** — `PERSON_NAME`, `ADDRESS`, `LOCATION`, `ORGANIZATION`, `DATE`, `AGE`,
`TIME`, `MONEY`, `PERCENT`, `FACILITY`, `GPE` (configurable via
`list_of_undeterministics_entities`; the list is injected into the response schema as an
enum, so the model cannot return a type outside it).

## Design notes

**Declaration order is priority.** Some values match several patterns — 11 bare digits
are both a CPF and a mobile number. The first pattern declared wins, so formatted
patterns come first and ambiguous bare numerics last.

**Longest value is replaced first, in a single pass.** The leading 12 digits of a spaced
credit card also match a voter ID. Replacing the shorter value first would corrupt the
longer one, and a single pass guarantees an inserted tag is never masked again.

**Values match on word boundaries.** `Ana` is masked in `Ana foi`, not inside `Mariana`.
Values that start or end with a symbol, such as `(27) 99999-8888`, get no boundary on
that side.

**Label-anchored patterns include the label.** `CNH`, `AGENCIA` and `CONTA_BANCARIA` mask
the label too (`CNH: 12345678901` → `[CNH_0]`), because the bare number is
indistinguishable from a CPF without it.

**LLM values absent from the text are discarded.** A paraphrased or invented value would
produce a no-op substitution while making the output *look* anonymized.

## Known limitations

- **Check digits are opt-in.** Without `strict=True`, a well-formed but arithmetically
  invalid CPF is still masked (over-detection is the safe side). `RG`, `PIS_PASEP` and
  `TITULO_ELEITOR` have no validator yet.
- **`DATA` matches any `dd/mm/aaaa` date**, with no way to tell a birth date from any
  other. Distinguishing them requires context, which is the LLM layer's job.
- **`US_ZIP` matches any 5-digit number**, and bare 11-digit runs are inherently
  ambiguous between CPF, CNH and mobile numbers.
- **`MONEY`, `PERCENT` and `TIME` are not PII** and only add noise. Adjust
  `list_of_undeterministics_entities` for your use case — the list is injected into the
  response schema as an enum, so it is the effective control over what the model may
  return.
- **Positional tags are not stable across texts.** Use `tag_style="hash"` if you need to
  correlate documents.
- **Tag numbering may skip an index.** When a short value is also a substring of a longer
  masked one, it stays registered to catch standalone occurrences elsewhere. Dropping it
  would leak PII.

## Tests

```bash
pip install -e ".[dev]"   # needs Python 3.9+, as declared in pyproject.toml
pytest        # 74 tests, hermetic: no server, no network (~3s)
pytest -m llm # 3 prompt-regression tests against a real Ollama
LLM_MODEL_NAME=qwen3:0.6b pytest -m llm   # pick the installed model
```

The default suite stubs every LLM response, so it needs no server. The `llm` marker is
deselected by default and holds the tests that call the model for real — they verify the
prompt rules still take effect, which a stub cannot do, and skip themselves when Ollama
or the model is unavailable.

## Layout

```text
src/anon_lib/__init__.py                 public API: Anonymizer, RecognizedEntity, __version__
src/anon_lib/anonymizer.py               Anonymizer
src/anon_lib/entities.py                 RecognizedEntity (type, value, start, end, score)
src/anon_lib/validators.py               CPF / CNPJ / Luhn check digits
src/anon_lib/patterns/patterns.py        regex pattern tables, per language
src/anon_lib/schemas/models_schemas.py   AnonOutput / PIIEntity (LLM response schema)
examples/demo.py                         runnable demo of both layers
tests/test_anonymizer.py                 test suite
```
