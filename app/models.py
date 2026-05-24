from pydantic import BaseModel, UUID4, Field
from typing import Optional
from datetime import datetime

class StepCreate(BaseModel):
    step_index:   int
    bearing_deg:  float = Field(ge=0, le=360)  # le not lt — 360 is valid
    distance_m:   float = Field(gt=0)           # removed le=50000 — historical routes exceed it
    label:        Optional[str]   = None
    description:  Optional[str]   = None
    image_url:    Optional[str]   = None
    pin_icon_id:  Optional[UUID4] = None
    pin_color:    str = "#378ADD"
    duration_sec: int = 0

class StepOut(StepCreate):
    id:         UUID4
    route_id:   UUID4
    created_at: datetime

class RouteCreate(BaseModel):
    title:              str = "Untitled Route"
    description:        Optional[str] = None
    cover_image_url:    Optional[str] = None
    origin_lat:         float
    origin_lng:         float
    origin_label:       Optional[str] = None
    origin_description: Optional[str] = None
    origin_duration:    int = 0
    is_public:          bool = False
    steps:              list[StepCreate] = []

class RouteUpdate(BaseModel):
    title:              Optional[str]   = None
    description:        Optional[str]   = None
    cover_image_url:    Optional[str]   = None
    is_public:          Optional[bool]  = None
    total_walked_m:     Optional[float] = None
    displacement_m:     Optional[float] = None
    drift_pct:          Optional[float] = None
    bearing_deg:        Optional[float] = None
    origin_label:       Optional[str]   = None
    origin_description: Optional[str]   = None
    origin_duration:    Optional[int]   = None
    model_config = {"from_attributes": True}

class RouteOut(BaseModel):
    id:                 UUID4
    user_id:            Optional[UUID4] = None
    title:              str
    description:        Optional[str]   = None
    cover_image_url:    Optional[str]   = None
    origin_lat:         float
    origin_lng:         float
    origin_label:       Optional[str]   = None
    origin_description: Optional[str]   = None
    origin_duration:    int = 0
    is_public:          bool
    total_walked_m:     Optional[float] = None
    displacement_m:     Optional[float] = None
    drift_pct:          Optional[float] = None
    bearing_deg:        Optional[float] = None
    view_count:         int
    fork_count:         int
    forked_from:        Optional[UUID4] = None
    created_at:         datetime
    updated_at:         datetime
    model_config = {"from_attributes": True}