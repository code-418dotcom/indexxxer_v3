from pydantic import BaseModel


class GalleryImageSchema(BaseModel):
    id: str
    gallery_id: str
    filename: str
    index_order: int
    width: int | None = None
    height: int | None = None

    model_config = {"from_attributes": True}


class GallerySchema(BaseModel):
    id: str
    source_id: str | None = None
    filename: str
    file_path: str
    image_count: int
    file_size: int | None = None
    file_mtime: str | None = None
    cover_url: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class GalleryDetailSchema(GallerySchema):
    images: list[GalleryImageSchema]
