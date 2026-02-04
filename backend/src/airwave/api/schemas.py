from typing import Optional

from pydantic import BaseModel


class ArtistStats(BaseModel):
    id: int
    name: str
    work_count: int
    recording_count: int
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True
