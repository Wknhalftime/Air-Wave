from typing import Optional

from pydantic import BaseModel, ConfigDict


class ArtistStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    work_count: int
    recording_count: int
    avatar_url: Optional[str] = None
