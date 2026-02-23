#!/usr/bin/env python3
"""CLI assistant for preparing Spanish manuscripts for English-language journals.

The workflow implements five stages:
1) Translation + language review
2) Abstract generation
3) Reference list formatting
4) Citation/reference consistency checks
5) Manuscript layout adaptation from journal instructions

Inputs and outputs follow the names requested by the user story.
"""

from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


# -------------------------------
# Optional third-party utilities
# -------------------------------

try:
    from deep_translator import GoogleTranslator  # type: ignore
except Exception:  # pragma: no cover
    GoogleTranslator = None

try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None

try:
    from docx import Document  # type: ignore
    from docx.shared import Pt  # type: ignore
except Exception:  # pragma: no cover
    Document = None
    Pt = None


@dataclass
class CitationCheckResult:
    unmatched_citations: list[str]
    uncited_references: list[str]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


# -------------------------------
# Stage 1 - Translation
# -------------------------------

def translate_spanish_to_english(text: str, dialect: str = "american") -> str:
    """Translate Spanish text to English.

    Uses deep_translator when available. If unavailable, returns the original
    text with a clear notice so the user can continue the pipeline.
    """
    if GoogleTranslator is None:
        return (
            "[NOTICE] deep_translator is not installed. Original text preserved for manual translation.\n\n"
            + text
        )

    translated = GoogleTranslator(source="es", target="en").translate(text)
    return apply_dialect_preferences(translated, dialect)


def apply_dialect_preferences(text: str, dialect: str) -> str:
    """Apply minimal lexical substitutions for dialect preference."""
    american_to_british = {
        "color": "colour",
        "behavior": "behaviour",
        "analyze": "analyse",
        "organize": "organise",
        "center": "centre",
        "modeling": "modelling",
        "labeled": "labelled",
    }

    if dialect.lower().startswith("brit"):
        for us_word, uk_word in american_to_british.items():
            text = re.sub(rf"\\b{us_word}\\b", uk_word, text, flags=re.IGNORECASE)
    return text


def review_academic_style(text: str) -> str:
    """Perform lightweight cleanup for grammar/scientific style."""
    replacements = {
        "In this work,": "In this study,",
        "a lot of": "many",
        "kind of": "type of",
        "very ": "",
        "we can see": "it is observed",
    }
    reviewed = text
    for source, target in replacements.items():
        reviewed = reviewed.replace(source, target)

    reviewed = re.sub(r"\s+", " ", reviewed).replace(" .", ".")
    reviewed = reviewed.replace(" ;", ";").replace(" ,", ",")
    reviewed = reviewed.replace("\n ", "\n")
    return reviewed.strip()


def stage1_translate(original_path: Path, output_main: Path, dialect: str) -> None:
    source_text = read_text(original_path)
    translated = translate_spanish_to_english(source_text, dialect=dialect)
    reviewed = review_academic_style(translated)
    write_text(output_main, reviewed)


# -------------------------------
# Stage 2 - Abstract
# -------------------------------

def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def generate_abstract(main_text: str, max_words: int = 250) -> str:
    """Heuristic abstract generation from key sections/sentences."""
    sentences = split_sentences(main_text)
    if not sentences:
        return ""

    # Prefer early context + objective markers + final conclusion
    objective = [s for s in sentences if re.search(r"\b(objective|aim|purpose|study)\b", s, re.I)]
    methods = [s for s in sentences if re.search(r"\b(method|approach|we used|analysis)\b", s, re.I)]
    results = [s for s in sentences if re.search(r"\b(result|found|showed|observed)\b", s, re.I)]
    conclusion = [s for s in sentences if re.search(r"\b(conclude|conclusion|therefore|suggest)\b", s, re.I)]

    selected: list[str] = []
    selected.extend(objective[:2] or sentences[:2])
    selected.extend(methods[:2])
    selected.extend(results[:2])
    if conclusion:
        selected.append(conclusion[0])
    elif len(sentences) > 2:
        selected.append(sentences[-1])

    abstract = " ".join(dict.fromkeys(selected))  # preserve order + dedupe

    words = abstract.split()
    if len(words) > max_words:
        abstract = " ".join(words[:max_words]).rstrip(".,;:") + "."

    return abstract


def stage2_abstract(main_path: Path, abstract_path: Path, max_words: int) -> None:
    main_text = read_text(main_path)
    abstract = generate_abstract(main_text, max_words=max_words)
    write_text(abstract_path, abstract)


# -------------------------------
# Stage 3 - Reference formatting
# -------------------------------

def parse_references(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    refs: list[str] = []
    buffer: list[str] = []

    for line in lines:
        if re.match(r"^(\[?\d+\]?\.|\[\d+\]|\d+\))\s+", line) and buffer:
            refs.append(" ".join(buffer).strip())
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        refs.append(" ".join(buffer).strip())
    return refs


def normalize_reference(ref: str) -> str:
    ref = re.sub(r"\s+", " ", ref).strip()
    ref = re.sub(r"\s+([,.;:])", r"\1", ref)
    return ref


def format_references(references: Sequence[str], style: str) -> list[str]:
    """Apply a lightweight style formatting wrapper.

    This does not attempt full bibliographic parsing; it standardizes numbering
    and punctuation so users can quickly refine edge cases.
    """
    cleaned = [normalize_reference(r) for r in references]
    style_key = style.lower()

    if style_key in {"vancouver", "numbered", "ieee"}:
        return [f"[{i}] {strip_existing_index(ref)}" for i, ref in enumerate(cleaned, 1)]
    if style_key in {"apa", "harvard", "author-year"}:
        return [strip_existing_index(ref) for ref in cleaned]
    if style_key in {"nature"}:
        return [f"{i}. {strip_existing_index(ref)}" for i, ref in enumerate(cleaned, 1)]

    # Fallback: keep content but ensure one reference per line
    return [strip_existing_index(ref) for ref in cleaned]


def strip_existing_index(ref: str) -> str:
    return re.sub(r"^(\[?\d+\]?\.|\[\d+\]|\d+\))\s*", "", ref).strip()


def stage3_format_references(input_refs: Path, output_refs: Path, style: str) -> None:
    refs_raw = read_text(input_refs)
    refs = parse_references(refs_raw)
    formatted = format_references(refs, style)
    write_text(output_refs, "\n".join(formatted))


# -------------------------------
# Stage 4 - Citation/reference checks
# -------------------------------

def citations_from_text(text: str, citation_format: str) -> list[str]:
    fmt = citation_format.lower()
    if fmt in {"vancouver", "numbered", "ieee", "nature"}:
        found = re.findall(r"\[(\d+)\]|\((\d+)\)", text)
        values = [a or b for a, b in found]
        return sorted(set(values), key=lambda x: int(x))

    # author-year style: captures entries like (Smith, 2020) or Smith et al., 2021
    found_parenthetical = re.findall(r"\(([A-ZÁÉÍÓÚÑ][^)]*?\d{4}[a-z]?)\)", text)
    found_inline = re.findall(r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\-]+(?:\s+et al\.)?,\s*\d{4}[a-z]?)", text)
    return sorted(set([f.strip() for f in found_parenthetical + found_inline]))


def references_keys(references: Sequence[str], citation_format: str) -> list[str]:
    fmt = citation_format.lower()
    keys: list[str] = []

    for i, ref in enumerate(references, start=1):
        if fmt in {"vancouver", "numbered", "ieee", "nature"}:
            m = re.match(r"^\[(\d+)\]|^(\d+)\.", ref)
            keys.append((m.group(1) or m.group(2)) if m else str(i))
            continue

        # author-year key (first author surname + year)
        year_match = re.search(r"(19|20)\d{2}[a-z]?", ref)
        surname_match = re.match(r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\-]+)", strip_existing_index(ref))
        if year_match and surname_match:
            keys.append(f"{surname_match.group(1)}, {year_match.group(0)}")
        else:
            keys.append(strip_existing_index(ref)[:40])

    return keys


def enforce_citation_format(main_text: str, citation_format: str) -> str:
    """Best-effort citation normalization.

    For numbered styles, convert '(n)' to '[n]'. For author-year, no automatic
    rewrite is attempted because it may require semantic parsing.
    """
    fmt = citation_format.lower()
    if fmt in {"vancouver", "numbered", "ieee", "nature"}:
        main_text = re.sub(r"\((\d+)\)", r"[\1]", main_text)
    return main_text


def stage4_check(
    main_path: Path,
    refs_corr_path: Path,
    citation_format: str,
    overwrite_main: bool = True,
) -> CitationCheckResult:
    main_text = read_text(main_path)
    refs = [line.strip() for line in read_text(refs_corr_path).splitlines() if line.strip()]

    normalized_main = enforce_citation_format(main_text, citation_format)
    if overwrite_main:
        write_text(main_path, normalized_main)

    citation_keys = citations_from_text(normalized_main, citation_format)
    reference_keys = references_keys(refs, citation_format)

    unmatched_citations = [c for c in citation_keys if c not in reference_keys]
    uncited_references = [r for r, key in zip(refs, reference_keys) if key not in citation_keys]

    return CitationCheckResult(
        unmatched_citations=unmatched_citations,
        uncited_references=uncited_references,
    )


# -------------------------------
# Stage 5 - Layout adaptation
# -------------------------------

def extract_layout_text(layout_pdf: Path) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(str(layout_pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def infer_layout_rules(layout_text: str) -> dict[str, str | int]:
    rules: dict[str, str | int] = {
        "font_name": "Times New Roman",
        "font_size": 12,
        "line_spacing": "double",
        "title_case": "sentence",
    }
    txt = layout_text.lower()

    if "arial" in txt:
        rules["font_name"] = "Arial"
    if "11 pt" in txt or "11-point" in txt:
        rules["font_size"] = 11
    if "single-spaced" in txt or "single spaced" in txt:
        rules["line_spacing"] = "single"
    if "title case" in txt:
        rules["title_case"] = "title"

    return rules


def to_docx(manuscript_txt: Path, output_docx: Path, rules: dict[str, str | int]) -> None:
    if Document is None or Pt is None:
        raise RuntimeError("python-docx is not installed. Install it to generate Paper.docx")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = str(rules["font_name"])
    style.font.size = Pt(int(rules["font_size"]))

    for raw_line in read_text(manuscript_txt).splitlines():
        line = raw_line.rstrip()
        if not line:
            doc.add_paragraph("")
            continue

        if line.isupper() or re.match(r"^(Abstract|Introduction|Methods?|Results?|Discussion|References)\b", line, re.I):
            p = doc.add_heading(line.title() if rules["title_case"] == "title" else line, level=1)
        else:
            p = doc.add_paragraph(line)

        if rules["line_spacing"] == "double":
            p.paragraph_format.line_spacing = 2.0
        else:
            p.paragraph_format.line_spacing = 1.0

    doc.save(str(output_docx))


def stage5_layout(manuscript_txt: Path, layout_pdf: Path, output_docx: Path) -> dict[str, str | int]:
    layout_text = extract_layout_text(layout_pdf)
    rules = infer_layout_rules(layout_text)
    to_docx(manuscript_txt, output_docx, rules)
    return rules


# -------------------------------
# CLI
# -------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assistant for preparing Spanish manuscripts for English-language journals.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("stage1", help="Translate Original.txt into Main.txt")
    p1.add_argument("--original", type=Path, default=Path("Original.txt"))
    p1.add_argument("--main", type=Path, default=Path("Main.txt"))
    p1.add_argument("--dialect", choices=["american", "british"], default="american")

    p2 = sub.add_parser("stage2", help="Generate Abstract.txt from Main.txt")
    p2.add_argument("--main", type=Path, default=Path("Main.txt"))
    p2.add_argument("--abstract", type=Path, default=Path("Abstract.txt"))
    p2.add_argument("--max-words", type=int, default=250)

    p3 = sub.add_parser("stage3", help="Format references into ReferencesCorr.txt")
    p3.add_argument("--references", type=Path, default=Path("References.txt"))
    p3.add_argument("--output", type=Path, default=Path("ReferencesCorr.txt"))
    p3.add_argument("--style", required=True, help="e.g., Vancouver, APA, Nature")

    p4 = sub.add_parser("stage4", help="Validate citations against references")
    p4.add_argument("--main", type=Path, default=Path("Main.txt"))
    p4.add_argument("--references", type=Path, default=Path("ReferencesCorr.txt"))
    p4.add_argument("--citation-format", required=True, help="numbered/Vancouver or author-year")

    p5 = sub.add_parser("stage5", help="Apply layout from Layout.pdf into Paper.docx")
    p5.add_argument("--manuscript", type=Path, default=Path("Manuscript.txt"))
    p5.add_argument("--layout", type=Path, default=Path("Layout.pdf"))
    p5.add_argument("--output", type=Path, default=Path("Paper.docx"))

    p_all = sub.add_parser("run-all", help="Run all stages in sequence")
    p_all.add_argument("--dialect", choices=["american", "british"], default="american")
    p_all.add_argument("--abstract-max-words", type=int, default=250)
    p_all.add_argument("--reference-style", required=True)
    p_all.add_argument("--citation-format", required=True)

    return parser


def run_all(args: argparse.Namespace) -> None:
    stage1_translate(Path("Original.txt"), Path("Main.txt"), args.dialect)
    stage2_abstract(Path("Main.txt"), Path("Abstract.txt"), args.abstract_max_words)
    stage3_format_references(Path("References.txt"), Path("ReferencesCorr.txt"), args.reference_style)
    result = stage4_check(Path("Main.txt"), Path("ReferencesCorr.txt"), args.citation_format)

    manuscript = Path("Manuscript.txt")
    combined = "\n\n".join([
        "ABSTRACT",
        read_text(Path("Abstract.txt")),
        "MAIN TEXT",
        read_text(Path("Main.txt")),
        "REFERENCES",
        read_text(Path("ReferencesCorr.txt")),
    ])
    write_text(manuscript, combined)

    if Path("Layout.pdf").exists():
        rules = stage5_layout(manuscript, Path("Layout.pdf"), Path("Paper.docx"))
        print(f"Stage 5 complete. Applied rules: {rules}")
    else:
        print("Stage 5 skipped: Layout.pdf not found.")

    print("Unmatched in-text citations:", result.unmatched_citations)
    print("Uncited references:", result.uncited_references)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "stage1":
        stage1_translate(args.original, args.main, args.dialect)
        print(f"Saved translated manuscript: {args.main}")
    elif args.command == "stage2":
        stage2_abstract(args.main, args.abstract, args.max_words)
        print(f"Saved abstract: {args.abstract}")
    elif args.command == "stage3":
        stage3_format_references(args.references, args.output, args.style)
        print(f"Saved formatted references: {args.output}")
    elif args.command == "stage4":
        result = stage4_check(args.main, args.references, args.citation_format)
        print("In-text citations lacking references:")
        print("\n".join(result.unmatched_citations) or "None")
        print("\nReferences lacking in-text citations:")
        print("\n".join(result.uncited_references) or "None")
    elif args.command == "stage5":
        rules = stage5_layout(args.manuscript, args.layout, args.output)
        print(f"Saved formatted paper: {args.output}")
        print(f"Applied inferred layout rules: {rules}")
    elif args.command == "run-all":
        run_all(args)


if __name__ == "__main__":
    main()
