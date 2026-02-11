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

# ✅ Regex سليم: رقم سداسي مستقل
CODE_RE = re.compile(r"\b(\d{6})\b")


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


@app.post("/api/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form(default="")
):
    try:
        data = await file.read()
        text = load_pdf_text_from_bytes(data)

        # 1) الأكواد السداسية
        codes = extract_codes(text)

        # 2) لو مفيش أكواد → اشتغل بالبراندات
        known_brands = [x.strip() for x in brands.split(",") if x.strip()]
        extracted_brands = []
        if not codes and known_brands:
            extracted_brands = extract_present_brands(text, known_brands)

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
