from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import require_auth
from app.services.supabase_client import supabase

router = APIRouter()


@router.get("/{username}")
def get_profile(username: str):
    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("username", username)
        .single()
        .execute()
    )
    if not profile.data:
        raise HTTPException(404, "Profile not found")

    routes = (
        supabase.table("routes")
        .select("*")
        .eq("user_id", profile.data["id"])
        .eq("is_public", True)
        .order("created_at", desc=True)
        .execute()
    )

    return {**profile.data, "routes": routes.data}


@router.get("/me/profile")
def get_my_profile(user: dict = Depends(require_auth)):
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user["sub"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Profile not found")
    return result.data