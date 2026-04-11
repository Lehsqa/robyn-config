import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OLD_FIELD_PATTERN = re.compile(r":\s*[^=\n]+=\s*Field\(")


def test_project_pydantic_models_use_annotated_field_syntax() -> None:
    offending_files: list[str] = []

    for path in sorted(ROOT.glob("src/**/*.py")) + sorted(
        ROOT.glob("src/**/*.jinja2")
    ):
        content = path.read_text()
        if OLD_FIELD_PATTERN.search(content):
            offending_files.append(str(path.relative_to(ROOT)))

    assert offending_files == []
