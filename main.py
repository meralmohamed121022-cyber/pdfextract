from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ممكن تخصص دومينك بعدين
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CODE_RE = re.compile(r"\((\d{5,7})\)")

def read_pdf_text_bytes(data: bytes) -> str:
    import io
    text_pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_pages.append(txt)
    return "\n".join(text_pages)

def split_blocks(text: str):
    blocks = []
    current = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks

def extract_code_from_block(block: str):
    m = CODE_RE.search(block)
    return m.group(1) if m else None

def extract_brands_from_text(text: str, known_brands):
    found = set()
    upper_text = text.upper()
    for b in known_brands:
        if b and len(b) > 2 and b.upper() in upper_text:
            found.add(b)
    return list(found)

@app.post("/api/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form(default="")
):
    try:
        data = await file.read()
        text = read_pdf_text_bytes(data)
        blocks = split_blocks(text)

        codes = []
        for b in blocks:
            c = extract_code_from_block(b)
            if c:
                codes.append(c)

        known_brands = [x.strip() for x in brands.split(",") if x.strip()]
        extracted_brands = extract_brands_from_text(text, known_brands) if known_brands else []

        return {
            "success": True,
            "codes": list(sorted(set(codes))),
            "brands": extracted_brands,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "codes": [],
            "brands": []
        }
