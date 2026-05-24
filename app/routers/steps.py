from fastapi import APIRouter, Depends, HTTPException
from app.models import StepCreate
from app.dependencies import require_auth
from app.services.supabase_client import supabase
import json

router = APIRouter()

def _jsonable(data):
    return json.loads(json.dumps(data, default=str))

def _assert_owner(route_id: str, user_sub: str):
    r = (
        supabase.table("routes")
        .select("user_id")
        .eq("id", route_id)
        .single()
        .execute()
    )
    if not r.data or r.data["user_id"] != user_sub:
        raise HTTPException(403, "Not your route")

@router.get("/{route_id}/steps")
def get_steps(route_id: str):
    result = (
        supabase.table("steps")
        .select("*")
        .eq("route_id", route_id)
        .order("step_index")
        .execute()
    )
    return _jsonable(result.data)

@router.put("/{route_id}/steps")
def replace_steps(
    route_id: str,
    steps: list[StepCreate],
    user: dict = Depends(require_auth),
):
    _assert_owner(route_id, user["sub"])
    supabase.table("steps").delete().eq("route_id", route_id).execute()
    if not steps:
        return []
    data = []
    for s in steps:
        step = {
            "route_id":    route_id,
            "step_index":  s.step_index,
            "bearing_deg": s.bearing_deg,
            "distance_m":  s.distance_m,
            "label":       s.label,
            "description": s.description,
            "image_url":   s.image_url,
            "pin_color":   s.pin_color,
            "duration_sec": s.duration_sec,
        }
        if s.pin_icon_id is not None:
            step["pin_icon_id"] = str(s.pin_icon_id)
        data.append({k: v for k, v in step.items() if v is not None})
    result = supabase.table("steps").insert(data).execute()
    return _jsonable(result.data)