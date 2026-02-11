from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader
import re
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ أكواد رقمية 5–8 أرقام جوه أقواس: (242140)
CODE_RE = re.compile(r"\((\d{5,8})\)")


def load_pdf_text_from_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages_text = []
    for page in reader.pages:
        t = page.extract_text() or ""
        pages_text.append(t)
    # ✅ newlines حقيقية
    text = "\n".join(pages_text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text


def extract_codes(text: str):
    # يطلع كل الأرقام بين الأقواس
    return sorted({m.group(1) for m in CODE_RE.finditer(text)})


def extract_present_brands(text: str, known_brands):
    upper_text = text.upper()
    found = set()
    for b in known_brands:
        if not b:
            continue
        name = b.strip()
        if len(name) < 3:
            continue
        if name.upper() in upper_text:
            found.add(name)
    return sorted(found)


def extract_brands_from_buy_lines(text: str):
    """
    أمثلة: Buy 1 DOVE Get 1 @ SAR 5.00 Feb, 25 - Mar, 05
    نستخرج DOVE
    """
    brands = set()
    for line in text.split("\n"):
        m = re.search(r"Buy\s+1\s+([A-Za-z0-9& ]+?)\s+Get\s+1", line, re.IGNORECASE)
        if m:
            brand = m.group(1).strip()
            if len(brand) >= 2:
                brands.add(brand)
    return sorted(brands)


@app.post("/api/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form(default="")
):
    try:
        data = await file.read()
        text = load_pdf_text_from_bytes(data)

        # 1) الأكواد من الأقواس (242140)
        codes = extract_codes(text)

        # 2) البراندات لو مفيش أكواد
        known_brands = [x.strip() for x in brands.split(",") if x.strip()]
        extracted_brands = []

        if not codes:
            if known_brands:
                extracted_brands = extract_present_brands(text, known_brands)
            if not extracted_brands:
                extracted_brands = extract_brands_from_buy_lines(text)

        return {
            "success": True,
            "codes": codes,
            "brands": extracted_brands,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "codes": [],
            "brands": []
        }
