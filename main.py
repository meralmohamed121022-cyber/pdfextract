from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import re

app = FastAPI()

# تفعيل CORS عشان موقعك يقدر يكلم السيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form("")  # استقبال البراندات كـ نص مفصول بفواصل
):
    try:
        # قراءة الملف في الذاكرة
        content = await file.read()
        
        all_text = ""
        
        # فتح ملف الـ PDF واستخراج النص صفحة بصفحة
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                # extract_text في بايثون ذكي جداً وبيجمع الحروف المتقطعة
                text = page.extract_text() or ""
                all_text += "\n" + text

        # --- 1. استخراج الأكواد ---
        # Regex يبحث عن 6 أرقام (سواء مستقلة أو داخل أقواس)
        code_pattern = re.compile(r'\b\d{6}\b')
        found_codes = code_pattern.findall(all_text)
        
        # تنظيف الأكواد (إزالة السنوات 2024-2030)
        unique_codes = set()
        for code in found_codes:
            num = int(code)
            if not (2024 <= num <= 2030):
                unique_codes.add(code)

        # --- 2. استخراج البراندات ---
        found_brands = set()
        if brands:
            brand_list = [b.strip() for b in brands.split(',') if len(b.strip()) > 2]
            upper_text = all_text.upper()
            
            for brand in brand_list:
                if brand.upper() in upper_text:
                    found_brands.add(brand)

        return {
            "success": True,
            "codes": list(unique_codes),
            "brands": list(found_brands),
            "count_codes": len(unique_codes),
            "count_brands": len(found_brands)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

# تشغيل السيرفر (لو بتجرب محلي)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)