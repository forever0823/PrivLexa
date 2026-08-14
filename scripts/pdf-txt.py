from __future__ import annotations

import argparse
import sys
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".docx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDF and DOCX files to UTF-8 text files."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="A PDF/DOCX file or a directory containing supported files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory used to store generated .txt files. Defaults to ./output.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively scan subdirectories when the input path is a directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser.parse_args()


def collect_source_files(input_path: Path, recursive: bool) -> list[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {input_path.suffix}")
        return [input_path]

    pattern = "**/*" if recursive else "*"
    files = [
        path
        for path in input_path.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files)


def extract_pdf_text(source_path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'pdfplumber'. Install it before converting PDF files."
        ) from exc

    pages: list[str] = []
    with pdfplumber.open(source_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def extract_docx_text(source_path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'python-docx'. Install it before converting DOCX files."
        ) from exc

    document = Document(source_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    return "\n".join(paragraphs)


def extract_text(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(source_path)
    if suffix == ".docx":
        return extract_docx_text(source_path)
    raise ValueError(f"Unsupported file type: {suffix}")


def build_output_path(source_path: Path, input_root: Path, output_dir: Path) -> Path:
    if input_root.is_file():
        relative_path = Path(source_path.stem)
    else:
        relative_path = source_path.relative_to(input_root).with_suffix("")
    return output_dir / relative_path.with_suffix(".txt")


def convert_file(
    source_path: Path, input_root: Path, output_dir: Path, overwrite: bool
) -> Path:
    output_path = build_output_path(source_path, input_root, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists. Use --overwrite to replace it: {output_path}"
        )

    text = extract_text(source_path)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()

    try:
        source_files = collect_source_files(args.input_path, args.recursive)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not source_files:
        print("No supported PDF or DOCX files were found.", file=sys.stderr)
        return 1

    success_count = 0
    failure_count = 0

    for source_path in source_files:
        try:
            output_path = convert_file(
                source_path=source_path,
                input_root=args.input_path,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
            )
            success_count += 1
            print(f"Converted: {source_path} -> {output_path}")
        except Exception as exc:
            failure_count += 1
            print(f"Failed: {source_path} ({exc})", file=sys.stderr)

    print(
        f"Finished. Success: {success_count}, Failed: {failure_count}, "
        f"Output: {args.output_dir}"
    )
    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
