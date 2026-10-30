from pydantic import BaseModel, ConfigDict, ValidationError


class ChunkRecord(BaseModel):
    """Schema of one silver chunk: required fields and their types (strict, no coercion)."""

    model_config = ConfigDict(strict=True, extra="ignore")

    chunk_id: str
    paper_key: str
    arxiv_id: str
    version: int
    title: str
    authors: list[str]
    section: str
    published_at: str
    chunk_index: int
    text: str
    text_hash: str
    n_words: int
    chunk_strategy: str
    pipeline_version: str
    run_date: str
    bronze_pdf_path: str | None = None


def schema_problems(row: dict) -> list[str]:
    """Reason codes like SCHEMA_title when a field is missing or has the wrong type."""
    try:
        ChunkRecord.model_validate(row)
    except ValidationError as exc:
        return sorted({"SCHEMA_" + ".".join(str(p) for p in err["loc"]) for err in exc.errors()})
    return []