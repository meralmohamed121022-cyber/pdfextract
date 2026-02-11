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
    نستخدمها لو الملف مافهوش ولا كود.
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

        # Debug: عدد الأكواد وأول 20 كود
        codes_count = len(codes)
        codes_sample = codes[:20]

        # Debug: أول 10 سطور فيها كود
        lines_with_codes = []
        for line in text.split("\n"):
            if CODE_RE.search(line):
                lines_with_codes.append(line.strip())
                if len(lines_with_codes) >= 10:
                    break

        # 2) لو الملف ده مافهوش ولا كود → نطلع البراندات
        known_brands = [x.strip() for x in brands.split(",") if x.strip()]
        extracted_brands = []

        if not codes:
            # أ) براندات من الـ DB لو بعتها من الفرونت
            if known_brands:
                extracted_brands = extract_present_brands(text, known_brands)
            # ب) لو لسه فاضي → براند من Buy 1 X Get 1
            if not extracted_brands:
                extracted_brands = extract_brands_from_buy_lines(text)

        return {
            "success": True,
            "codes": codes,
            "brands": extracted_brands,
            "debug": {
                "codes_count": codes_count,
                "codes_sample": codes_sample,
                "lines_with_codes": lines_with_codes,
                "text_snippet": text[:1000]
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "codes": [],
            "brands": [],
            "debug": {}
        }
