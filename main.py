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

# ===================== HELPERS =====================

def format_price_arabic(price_str: str):
    price_float = float(price_str)
    if price_float == int(price_float):
        return str(int(price_float))
    else:
        return price_str

def normalize_price_from_line(line: str):
    m = re.search(r"@ *SAR *(\d+(?:\.\d{1,2})?)", line)
    if m:
        return f"{float(m.group(1)):.2f}"
    return None

def extract_brand_from_buy1(line: str):
    m = re.search(r"Buy 1\s+(.+?)\s+Get 1", line)
    if not m:
        return None
    return m.group(1).strip()

def load_pdf_text_from_bytes(data: bytes) -> str:
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

# ===================== CORE EXTRACT LOGIC =====================

def extract_offers_from_text(text: str):
    # 1) NON-CODED OFFERS (Buy 1 Get 1 بدون أكواد)
    non_coded_offers = []
    seen_offers = set()

    for line in text.split("\n"):
        if not ("Buy 1" in line and "Get 1" in line):
            continue
        if re.search(r"\b\d{6}\b", line):
            continue

        brand = extract_brand_from_buy1(line)
        if not brand:
            continue

        price = normalize_price_from_line(line)
        if price is not None:
            offer_type = f"Buy 1 Get 1 @ SAR {price}"
            price_ar = format_price_arabic(price)
            offer_type_ar = f"اشتري 1 واحصل على 1 بـ {price_ar} ريال"
        else:
            if not re.search(r"Get 1\s+Free", line, re.IGNORECASE):
                continue
            offer_type = "Buy 1 Get 1 Free"
            offer_type_ar = "اشتري 1 واحصل على 1 مجانًا"

        key = (offer_type, brand)
        if key in seen_offers:
            continue
        seen_offers.add(key)

        non_coded_offers.append({
            "offerType": offer_type,
            "offerTypeAR": offer_type_ar,
            "codes": [brand]
        })

    # 2) CODED OFFERS (السعر المشطوب + Buy X Get Y مع أكواد)
    coded_price_map = {}
    coded_buyget_map = {}

    # (أ) عروض السعر الجديد/القديم – هنا هنشيل شرط DATE_PATTERN ونكتفي بـ pattern عام
    price_blocks = re.finditer(
        r"([A-Z][A-Z\s,&]+?)\s+"                      # Category
        r"(\d{1,4}\.\d{2})\s+(\d{1,4}\.\d{2})"       # new_price old_price
        r"(.*?)(?=\n[A-Z][A-Z\s,&]+?\s+(?:\d{1,2}% Discount|\d{1,4}\.\d{2}\s+\d{1,4}\.\d{2}|Buy \d+ )|$)",
        text,
        re.DOTALL
    )

    for m in price_blocks:
        new_price = m.group(2)
        tail = m.group(4)
        codes_found = re.findall(r"\b(\d{6})\b", tail)
        if codes_found:
            coded_price_map.setdefault(new_price, set()).update(codes_found)

    # (ب) عروض Buy X Get Y اللي فيها أكواد
    for line in text.split("\n"):
        if not ("Buy" in line and "Get" in line):
            continue
        codes_in_line = re.findall(r"\b(\d{6})\b", line)
        if not codes_in_line:
            continue
        if re.search(r"\d{1,2}% Discount", line):
            continue
        if re.search(r"\d{1,4}\.\d{2}\s+\d{1,4}\.\d{2}", line):
            continue

        buy_pattern = re.search(
            r"(Buy \d+(?:\s+\w+)?\s+Get \d+(?:\s+(?:Free|@?\s*SAR\s*\d+(?:\.\d{2})?))?)",
            line,
            re.IGNORECASE
        )
        if buy_pattern:
            offer_text = buy_pattern.group(1).strip()
            offer_text = re.sub(r"\s+", " ", offer_text)
            for code in codes_in_line:
                coded_buyget_map.setdefault(offer_text, set()).add(code)

    coded_offers = []

    # أولاً: عروض السعر
    for new_price in sorted(coded_price_map.keys(), key=lambda x: float(x)):
        codes = sorted(coded_price_map[new_price])
        offer_price_map = {code: float(new_price) for code in codes}
        price_ar = format_price_arabic(new_price)
        coded_offers.append({
            "offerType": f"Buy 1 @ SAR {new_price}",
            "offerTypeAR": f"احصل على الحبة ب {price_ar} ريال",
            "codes": codes,
            "styleClass": "offer-fixed-price",
            "badgeClass": "offer-fixed-price",
            "offerPrice": offer_price_map
        })

    # ثانياً: عروض Buy X Get Y
    for offer_text in sorted(coded_buyget_map.keys()):
        codes = sorted(coded_buyget_map[offer_text])
        offer_type_ar = (
            offer_text
            .replace("Buy", "اشتري")
            .replace("Get", "واحصل على")
            .replace("Free", "مجانًا")
        )
        if "SAR" in offer_text:
            price_match = re.search(r"SAR\s*(\d+(?:\.\d{2})?)", offer_text)
            if price_match:
                price_str = price_match.group(1)
                price_ar = format_price_arabic(price_str)
                offer_type_ar = offer_type_ar.replace(f"SAR {price_str}", f"بـ {price_ar}").replace("@", "")

        style_slug = (
            offer_text.lower()
            .replace(" ", "-")
            .replace("@", "")
            .replace(".", "")
        )

        coded_offers.append({
            "offerType": offer_text,
            "offerTypeAR": offer_type_ar,
            "codes": codes,
            "styleClass": style_slug,
            "badgeClass": style_slug,
            "offerPrice": {}
        })

    return non_coded_offers, coded_offers

# ===================== FASTAPI ENDPOINT =====================

@app.post("/api/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form(default="")
):
    try:
        data = await file.read()
        text = load_pdf_text_from_bytes(data)
        non_coded, coded = extract_offers_from_text(text)

        # نطلع كل الأكواد من coded_offers
        all_codes = sorted({c for offer in coded for c in offer.get("codes", [])})

        return {
            "success": True,
            "non_coded_offers": non_coded,
            "coded_offers": coded,
            "codes": all_codes,
            "brands": []  # تقدر تزود logic للبراندات لو حابب
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "non_coded_offers": [],
            "coded_offers": [],
            "codes": [],
            "brands": []
        }
