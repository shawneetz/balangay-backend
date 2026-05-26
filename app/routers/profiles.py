from fastapi import APIRouter, HTTPException, Depends
from postgrest.exceptions import APIError
from app.services.supabase_client import supabase
from app.dependencies import require_auth, get_current_user

router = APIRouter()

@router.get("/by-id/{user_id}")
def get_profile_by_id(user_id: str, user: dict = Depends(require_auth)):
    if user["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    except APIError:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data

@router.get("/{username}")
def get_profile(username: str, user: dict | None = Depends(get_current_user)):
    try:
        result = (
            supabase.table("profiles")
            .select("*")
            .eq("username", username)
            .single()
            .execute()
        )
    except APIError:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = result.data
    is_owner = user is not None and user["sub"] == profile["id"]

    # Public routes — visible to everyone
    public_routes_result = (
        supabase.table("routes")
        .select("*")
        .eq("user_id", profile["id"])
        .eq("is_public", True)
        .order("created_at", desc=True)
        .execute()
    )

    # Private routes — only returned when the requester is the owner
    private_routes = []
    if is_owner:
        private_routes_result = (
            supabase.table("routes")
            .select("*")
            .eq("user_id", profile["id"])
            .eq("is_public", False)
            .order("created_at", desc=True)
            .execute()
        )
        private_routes = private_routes_result.data or []

    return {
        **profile,
        "routes": public_routes_result.data or [],
        "private_routes": private_routes,
        "is_owner": is_owner,
    }