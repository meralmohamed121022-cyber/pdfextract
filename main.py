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

# ✅ أي رقم سداسي مستقل في النص (107338, 206746, 234549, ...)
CODE_RE = re.compile(r"\b(\d{6})\b")


def load_pdf_text_from_bytes(data: bytes) -> str:
    """قراءة كل صفحات الـ PDF كنص واحد منظم."""
    reader = PdfReader(io.BytesIO(data))
    pages_text = []
    for page in reader.pages:
        t = page.extract_text() or ""
        pages_text.append(t)
    text = "\n".join(pages_text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text


def extract_codes(text: str):
    """يرجع كل الأكواد السداسية الموجودة في أي مكان في النص."""
    return sorted({m.group(1) for m in CODE_RE.finditer(text)})


def extract_present_brands(text: str, known_brands):
    """
    يشيك البراندات اللي جايه من الفرونت (productsDB) جوه النص.
    نستخدمها كجزء من البراندات لو الملف فيه كروت بدون كود.
    """
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
    يمسك السطور اللي بالشكل:
    Buy 1 DOVE Get 1 @ SAR 5.00 ...
    بشرط إن السطر نفسه ما فيهوش كود سداسي (يعني كرت بدون كود).
    """
    brands = set()
    for line in text.split("\n"):
        # لو السطر فيه كود، يبقى كرت بكود نسيبه للأكواد
        if CODE_RE.search(line):
            continue
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

        # 1) استخرج كل الأكواد السداسية من الكروت اللي فيها أكواد
        codes = extract_codes(text)

        # 2) استخرج البراندات من الكروت اللي مافيهاش كود + من قائمة البراندات لو مبعوتة
        known_brands = [x.strip() for x in brands.split(",") if x.strip()]

        brands_from_db = extract_present_brands(text, known_brands) if known_brands else []
        brands_from_buy = extract_brands_from_buy_lines(text)

        all_brands = sorted({*brands_from_db, *brands_from_buy})

        return {
            "success": True,
            "codes": codes,
            "brands": all_brands,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "codes": [],
            "brands": []
        }
