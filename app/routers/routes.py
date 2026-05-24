from fastapi import APIRouter, Depends, HTTPException, Query
from app.models import RouteCreate, RouteUpdate
from app.dependencies import get_current_user, require_auth
from app.services.supabase_client import supabase
import json

router = APIRouter()

def _jsonable(data):
    return json.loads(json.dumps(data, default=str))

@router.get("/")
def list_public_routes(
    limit: int = Query(20, le=100),
    offset: int = 0,
    user: dict | None = Depends(get_current_user),
):
    result = (
        supabase.table("routes")
        .select("*")
        .eq("is_public", True)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return _jsonable(result.data)

@router.get("/mine")
def list_my_routes(user: dict = Depends(require_auth)):
    result = (
        supabase.table("routes")
        .select("*")
        .eq("user_id", user["sub"])
        .order("updated_at", desc=True)
        .execute()
    )
    return _jsonable(result.data)

@router.post("/")
def create_route(payload: RouteCreate, user: dict = Depends(require_auth)):
    route_data = {
        "user_id":             user["sub"],
        "title":               payload.title,
        "description":         payload.description,
        "cover_image_url":     payload.cover_image_url,
        "origin_lat":          payload.origin_lat,
        "origin_lng":          payload.origin_lng,
        "origin_label":        payload.origin_label,
        "origin_description":  payload.origin_description,
        "origin_duration":     payload.origin_duration,
        "is_public":           payload.is_public,
    }
    route_data = {k: v for k, v in route_data.items() if v is not None}

    route_res = supabase.table("routes").insert(route_data).execute()
    if not route_res.data:
        raise HTTPException(500, "Failed to create route")
    route = route_res.data[0]  # type: ignore

    if payload.steps:
        steps_data = []
        for s in payload.steps:
            step = {
                "route_id":    route["id"],
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
            steps_data.append({k: v for k, v in step.items() if v is not None})
        supabase.table("steps").insert(steps_data).execute()

    return _jsonable(route)

@router.get("/{route_id}")
def get_route(route_id: str, user: dict | None = Depends(get_current_user)):
    result = (
        supabase.table("routes").select("*").eq("id", route_id).single().execute()
    )
    if not result.data:
        raise HTTPException(404, "Route not found")
    route = result.data  # type: ignore
    if not route["is_public"] and (not user or user["sub"] != route["user_id"]):
        raise HTTPException(403, "Private route")
    supabase.table("routes").update(
        {"view_count": route["view_count"] + 1}
    ).eq("id", route_id).execute()
    return _jsonable(route)

@router.put("/{route_id}")
def update_route(
    route_id: str,
    payload: RouteUpdate,
    user: dict = Depends(require_auth),
):
    existing = (
        supabase.table("routes")
        .select("user_id")
        .eq("id", route_id)
        .single()
        .execute()
    )
    if not existing.data or existing.data["user_id"] != user["sub"]:  # type: ignore
        raise HTTPException(403, "Not your route")
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not update_data:
        raise HTTPException(400, "No fields to update")
    result = (
        supabase.table("routes").update(update_data).eq("id", route_id).execute()
    )
    return _jsonable(result.data[0])  # type: ignore

@router.delete("/{route_id}", status_code=204)
def delete_route(route_id: str, user: dict = Depends(require_auth)):
    existing = (
        supabase.table("routes")
        .select("user_id")
        .eq("id", route_id)
        .single()
        .execute()
    )
    if not existing.data or existing.data["user_id"] != user["sub"]:  # type: ignore
        raise HTTPException(403, "Not your route")
    supabase.table("routes").delete().eq("id", route_id).execute()

@router.post("/{route_id}/fork")
def fork_route(route_id: str, user: dict = Depends(require_auth)):
    orig = (
        supabase.table("routes").select("*").eq("id", route_id).single().execute()
    )
    if not orig.data or not orig.data["is_public"]:
        raise HTTPException(404, "Route not found or not public")

    orig_steps = (
        supabase.table("steps")
        .select("*")
        .eq("route_id", route_id)
        .order("step_index")
        .execute()
    )

    copy_fields = [
        "title", "description", "cover_image_url",
        "origin_lat", "origin_lng",
        "origin_label", "origin_description", "origin_duration",
        "total_walked_m", "displacement_m", "drift_pct", "bearing_deg",
    ]
    new_route = {k: orig.data[k] for k in copy_fields if orig.data.get(k) is not None}
    new_route["user_id"]     = user["sub"]
    new_route["is_public"]   = False
    new_route["title"]       = f"Fork of {orig.data['title']}"
    new_route["forked_from"] = route_id
    new_route["view_count"]  = 0
    new_route["fork_count"]  = 0
    created = supabase.table("routes").insert(new_route).execute().data[0]  # type: ignore

    if orig_steps.data:
        step_fields = [
            "step_index", "bearing_deg", "distance_m",
            "label", "description", "image_url", "pin_color", "duration_sec",
        ]
        new_steps = [
            {k: s[k] for k in step_fields if s.get(k) is not None}
            | {"route_id": created["id"]}
            for s in orig_steps.data
        ]
        supabase.table("steps").insert(new_steps).execute()

    supabase.table("routes").update(
        {"fork_count": orig.data["fork_count"] + 1}
    ).eq("id", route_id).execute()

    return _jsonable(created)