## Sentence-anonimizer

This project focus on data anonimization of sensible data.


You can fine-tune your own transformer-bassed model, but you need to create your dataset.

Example:
```
    input: "My name is Mary, 35 years old and daugther of Joshua Smith."
    output: {
        "PERSON": "Mary",
        "AGE": "35 years old",
        "PERSON": "daugther of Joshua Smith"
    }
```

Support to Brazilian portuguese and English