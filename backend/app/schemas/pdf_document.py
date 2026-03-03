from pydantic import BaseModel


class PDFDocumentSchema(BaseModel):
    id: str
    source_id: str | None = None
    filename: str
    file_path: str
    title: str | None = None
    page_count: int
    file_size: int | None = None
    file_mtime: str | None = None
    cover_url: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
