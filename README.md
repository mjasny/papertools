# Paper Tools

## Installation:

- `python -m venv venv`
- `source venv/bin/activate`
- `pip install -r requirements.txt`


## Rephraser

### Example:

`(venv)$ python rephraser.py ~/repositories/overleaf_paper/main.tex`

### Usage:

```
usage: rephraser.py [-h] [--skip-abstract] [--skip-captions] [--skip-sections] [-r REPL] main.tex

positional arguments:
  main.tex              Main file of Latex project.

optional arguments:
  -h, --help            show this help message and exit
  --skip-abstract       Skip abstract.
  --skip-captions       Skip sub(captions) of figures.
  --skip-sections       Skip all sections.
  -r REPL, --repl REPL  Replace within latex source: -r "\system{}=Test" (multiple)
```