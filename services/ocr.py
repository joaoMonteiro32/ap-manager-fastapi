import re
from io import BytesIO
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from pyzbar.pyzbar import decode

MAC_LINE_REGEX = re.compile(
    r"\bMAC\s*[:=]?\s*([0-9A-Fa-f]{2}(?:[:-]?[0-9A-Fa-f]{2}){5})\b",
    re.IGNORECASE,
)

HEX12_REGEX = re.compile(r"^[0-9A-Fa-f]{12}$")


def normalize_mac(mac: str, allow_compact: bool = False) -> str | None:
    if not mac:
        return None

    mac = mac.upper().replace(":", "").replace("-", "").replace(" ", "").strip()

    if len(mac) != 12:
        return None

    if not all(c in "0123456789ABCDEF" for c in mac):
        return None

    if allow_compact:
        return mac

    return "-".join(mac[i:i+2] for i in range(0, 12, 2))


def _prepare_image(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    max_size = 2200
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    return img


def _candidate_crops(img: Image.Image):
    w, h = img.size
    return [
        img.crop((int(w * 0.15), int(h * 0.08), int(w * 0.82), int(h * 0.92))),
        img.crop((int(w * 0.30), int(h * 0.10), int(w * 0.98), int(h * 0.80))),
        img.crop((int(w * 0.08), int(h * 0.30), int(w * 0.92), int(h * 0.78))),
    ]


def _decode_barcode_candidates(img: Image.Image):
    results = []

    try:
        decoded = decode(img)
        for d in decoded:
            raw = ""
            try:
                raw = d.data.decode("utf-8").strip()
            except Exception:
                continue

            cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw)

            score = 0

            # MAC típico = 12 hex chars
            if len(cleaned) == 12 and HEX12_REGEX.match(cleaned):
                score += 100

            # Line barcode costuma ser melhor para MAC do que QR do device key
            if d.type in {"CODE128", "CODE39", "EAN13", "EAN8"}:
                score += 20
            elif d.type == "QRCODE":
                score -= 10

            # valores mais longos costumam ser device key / GPON / serial
            if len(cleaned) != 12:
                score -= 50

            results.append((score, raw))
    except Exception:
        pass

    results.sort(key=lambda x: x[0], reverse=True)
    return [raw for score, raw in results if score > 0]


def _image_variants(img: Image.Image):
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)

    scale = 3
    big = gray.resize((gray.width * scale, gray.height * scale))

    sharp = big.filter(ImageFilter.SHARPEN)
    bw1 = sharp.point(lambda p: 255 if p > 150 else 0)
    bw2 = sharp.point(lambda p: 255 if p > 180 else 0)

    return [big, sharp, bw1, bw2]


def _ocr_texts(img: Image.Image):
    texts = []
    for variant in _image_variants(img):
        for psm in (6, 11):
            try:
                text = pytesseract.image_to_string(variant, config=f"--psm {psm}")
                if text and text.strip():
                    texts.append(text)
            except Exception:
                pass
    return texts


def _extract_mac_from_text(text: str) -> str | None:
    m = MAC_LINE_REGEX.search(text)
    if not m:
        return None
    return normalize_mac(m.group(1), allow_compact=False)


def extract_mac_from_bytes(file_bytes: bytes) -> str | None:
    try:
        img = Image.open(BytesIO(file_bytes))
        img = _prepare_image(img)
    except Exception:
        return None

    # 1) barcode first
    for crop in _candidate_crops(img):
        for candidate in _decode_barcode_candidates(crop):
            mac = normalize_mac(candidate, allow_compact=False)
            if mac:
                return mac

    # 2) OCR fallback by explicit MAC line
    for crop in _candidate_crops(img):
        for text in _ocr_texts(crop):
            mac = _extract_mac_from_text(text)
            if mac:
                return mac

    return None