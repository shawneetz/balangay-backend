import io
import uuid
import xml.etree.ElementTree as ET
from PIL import Image
import scour.scour as scour_lib
from app.services.supabase_client import supabase

MAX_IMAGE_DIM = 1200
PIN_DIM = 64

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PIN_TYPES = {"image/svg+xml", "image/png"}

# All SVG tags and attributes we allow — everything else gets stripped
SAFE_SVG_TAGS = {
    "svg", "g", "path", "circle", "rect", "ellipse", "line",
    "polyline", "polygon", "text", "tspan", "defs", "clipPath",
    "use", "symbol", "linearGradient", "radialGradient", "stop",
    "mask", "pattern", "title", "desc", "style",
}

SAFE_SVG_ATTRS = {
    "id", "class", "style", "transform", "clip-path", "mask",
    "opacity", "fill", "fill-opacity", "fill-rule", "stroke",
    "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-opacity", "stroke-dasharray", "stroke-dashoffset",
    "d", "cx", "cy", "r", "x", "y", "x1", "y1", "x2", "y2",
    "rx", "ry", "width", "height", "points", "viewBox", "xmlns",
    "version", "preserveAspectRatio", "offset", "stop-color",
    "stop-opacity", "href", "gradientUnits", "gradientTransform",
    "spreadMethod", "patternUnits", "patternTransform",
    "text-anchor", "dominant-baseline", "font-size",
    "font-family", "font-weight", "dx", "dy",
}


def _strip_svg_namespace(tag: str) -> str:
    """Remove XML namespace prefix from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def sanitize_svg(data: bytes) -> bytes:
    """
    Strip unsafe tags and attributes from SVG using stdlib xml.etree.ElementTree.
    Removes script tags, event handlers (on*), and javascript: hrefs.
    Then optimizes with scour.
    """
    try:
        root = ET.fromstring(data.decode("utf-8", errors="replace"))
    except ET.ParseError:
        raise ValueError("Invalid SVG: could not parse XML")

    def clean_element(el):
        # Strip any on* event handler attributes and javascript: hrefs
        bad_attrs = [
            k for k in list(el.attrib)
            if k.lower().startswith("on")
            or (k.lower() in ("href", "xlink:href")
                and str(el.attrib[k]).strip().lower().startswith("javascript"))
        ]
        for k in bad_attrs:
            del el.attrib[k]

        # Remove attributes not in the safe list
        for k in list(el.attrib):
            local = k.split("}")[-1] if "}" in k else k
            if local not in SAFE_SVG_ATTRS:
                del el.attrib[k]

        # Recurse, removing children with unsafe tags
        for child in list(el):
            local_tag = _strip_svg_namespace(child.tag)
            if local_tag.lower() == "script":
                el.remove(child)
            elif local_tag not in SAFE_SVG_TAGS:
                el.remove(child)
            else:
                clean_element(child)

    clean_element(root)

    cleaned_bytes = ET.tostring(root, encoding="unicode").encode("utf-8")

    # Optimize with scour
    options = scour_lib.sanitizeOptions()
    options.remove_metadata = True
    options.enable_viewboxing = True
    options.strip_comments = True
    options.strip_ids = False
    result = scour_lib.scourString(cleaned_bytes.decode("utf-8"), options)
    return result.encode("utf-8")


def compress_image(data: bytes, mime: str) -> bytes:
    """Resize to MAX_IMAGE_DIM and compress."""
    img = Image.open(io.BytesIO(data))
    if mime == "image/png":
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if mime == "image/png":
        img.save(buf, "PNG", optimize=True)
    else:
        img = img.convert("RGB")
        img.save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue()


def upload_to_storage(bucket: str, path: str, data: bytes, content_type: str) -> str:
    """Upload bytes to Supabase Storage and return the public URL."""
    supabase.storage.from_(bucket).upload(
        path,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    url = supabase.storage.from_(bucket).get_public_url(path)
    return url