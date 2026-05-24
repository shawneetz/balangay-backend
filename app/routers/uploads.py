import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.dependencies import require_auth
from app.services.supabase_client import supabase
from app.services.image_service import (
    compress_image,
    sanitize_svg,
    upload_to_storage,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_PIN_TYPES,
    PIN_DIM,
)
from PIL import Image

router = APIRouter()


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    """Upload a step or cover image. Returns the public URL."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(415, f"Unsupported type. Allowed: {ALLOWED_IMAGE_TYPES}")

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 5MB limit")

    compressed = compress_image(raw, content_type)
    ext = "png" if content_type == "image/png" else "jpg"
    path = f"{user['sub']}/{uuid.uuid4()}.{ext}"
    url = upload_to_storage("route-images", path, compressed, content_type)
    return {"url": url}


@router.post("/pin-icon")
async def upload_pin_icon(
    file: UploadFile = File(...),
    name: str = Form(default="Custom pin"),
    user: dict = Depends(require_auth),
):
    """Upload a custom pin icon (SVG or PNG). Sanitised and normalised to 64×64px."""
    content_type = file.content_type or ""

    # Some browsers send text/xml for SVGs — normalise by filename
    if file.filename and file.filename.lower().endswith(".svg"):
        content_type = "image/svg+xml"

    if content_type not in ALLOWED_PIN_TYPES:
        raise HTTPException(415, "Pin icons must be SVG or PNG")

    raw = await file.read()
    if len(raw) > 512 * 1024:
        raise HTTPException(413, "Pin icon exceeds 512KB limit")

    file_type = "svg" if content_type == "image/svg+xml" else "png"

    if file_type == "svg":
        try:
            processed = sanitize_svg(raw)
        except ValueError as e:
            raise HTTPException(422, str(e))
        ext = "svg"
        store_content_type = "image/svg+xml"
    else:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img = img.resize((PIN_DIM, PIN_DIM), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        processed = buf.getvalue()
        ext = "png"
        store_content_type = "image/png"

    path = f"{user['sub']}/{uuid.uuid4()}.{ext}"
    url = upload_to_storage("pin-icons", path, processed, store_content_type)

    record = supabase.table("pin_icons").insert({
        "user_id": user["sub"],
        "name": name,
        "file_url": url,
        "file_type": file_type,
        "width_px": PIN_DIM,
        "height_px": PIN_DIM,
    }).execute()

    return {
        "url": url,
        "id": record.data[0]["id"],
        "file_type": file_type,
    }


@router.get("/pin-icons/mine")
def get_my_pins(user: dict = Depends(require_auth)):
    result = (
        supabase.table("pin_icons")
        .select("*")
        .eq("user_id", user["sub"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/pin-icons/{pin_id}", status_code=204)
def delete_pin(pin_id: str, user: dict = Depends(require_auth)):
    record = (
        supabase.table("pin_icons")
        .select("user_id, file_url")
        .eq("id", pin_id)
        .single()
        .execute()
    )
    if not record.data or record.data["user_id"] != user["sub"]:
        raise HTTPException(403, "Not yours")

    # Extract storage path from URL and delete from bucket
    url: str = record.data["file_url"]
    path = url.split("/object/public/pin-icons/")[-1]
    supabase.storage.from_("pin-icons").remove([path])
    supabase.table("pin_icons").delete().eq("id", pin_id).execute()