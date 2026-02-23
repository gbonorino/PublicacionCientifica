# PublicacionCientifica Assistant

`manuscript_assistant.py` is a command-line Python tool that supports Spanish-speaking scientists in preparing manuscripts for English-language journals.

## Workflow implemented

1. **Stage 1 – Translation** (`Original.txt` -> `Main.txt`)
   - Translates Spanish text + figure legends to English.
   - Supports British/American dialect preference.
   - Applies a lightweight scientific-language cleanup.

2. **Stage 2 – Abstract generation** (`Main.txt` -> `Abstract.txt`)
   - Generates an English abstract from the translated manuscript.
   - Supports maximum word count.

3. **Stage 3 – Reference formatting** (`References.txt` -> `ReferencesCorr.txt`)
   - Reformats references according to style (e.g., Vancouver, APA, Nature).

4. **Stage 4 – Citation/reference consistency checks**
   - Checks and normalizes in-text citation style.
   - Reports citations without matching references.
   - Reports references that are never cited in the text.

5. **Stage 5 – Final layout** (`Manuscript.txt` + `Layout.pdf` -> `Paper.docx`)
   - Infers formatting rules from the journal instructions PDF.
   - Applies formatting to generate `Paper.docx`.

## Installation

Python 3.10+ recommended.

Optional dependencies:

```bash
pip install deep-translator pypdf python-docx
```

- `deep-translator`: used for machine translation.
- `pypdf`: used to read `Layout.pdf` instructions.
- `python-docx`: required to create `Paper.docx`.

If optional dependencies are missing, stages may use fallbacks or print clear error messages.

## Usage

```bash
python manuscript_assistant.py --help
```

Run one stage at a time:

```bash
python manuscript_assistant.py stage1 --original Original.txt --main Main.txt --dialect british
python manuscript_assistant.py stage2 --main Main.txt --abstract Abstract.txt --max-words 250
python manuscript_assistant.py stage3 --references References.txt --output ReferencesCorr.txt --style Vancouver
python manuscript_assistant.py stage4 --main Main.txt --references ReferencesCorr.txt --citation-format Vancouver
python manuscript_assistant.py stage5 --manuscript Manuscript.txt --layout Layout.pdf --output Paper.docx
```

Or run all stages in sequence:

```bash
python manuscript_assistant.py run-all --dialect american --abstract-max-words 250 --reference-style Vancouver --citation-format Vancouver
```

## Expected files

- Input: `Original.txt`, `References.txt`, `Layout.pdf` (for stage 5), and optionally `Manuscript.txt` (if running stage 5 directly).
- Output: `Main.txt`, `Abstract.txt`, `ReferencesCorr.txt`, and `Paper.docx`.
