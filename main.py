from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import re

app = FastAPI()

# تفعيل CORS للسماح للموقع بالاتصال بالسيرفر
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # السماح لأي دومين
    allow_credentials=True,
    allow_methods=["*"],  # السماح بكل العمليات (POST, OPTIONS, etc)
    allow_headers=["*"],
)

@app.post("/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    brands: str = Form("")  # استقبال البراندات كنص
):
    try:
        # 1. قراءة محتوى الملف في الذاكرة
        content = await file.read()
        all_text = ""
        
        # 2. استخدام pdfplumber لاستخراج النصوص بدقة عالية
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += "\n" + text

        # 3. استخراج الأكواد السداسية (Regex قوي جداً)
        # يبحث عن 6 أرقام متتالية لا يسبقها ولا يليها رقم
        # هذا يلتقط (123456) و Code:123456 وغيرها
        code_pattern = re.compile(r'(?<!\d)\d{6}(?!\d)')
        found_codes = code_pattern.findall(all_text)
        
        # 4. تنظيف الأكواد (إزالة السنوات 2024-2030)
        unique_codes = set()
        for code in found_codes:
            num = int(code)
            # استبعاد الأرقام التي تمثل سنوات العروض
            if not (2024 <= num <= 2030):
                unique_codes.add(code)

        # 5. استخراج البراندات (بحث ذكي)
        found_brands = set()
        if brands:
            # تنظيف قائمة البراندات المرسلة
            brand_list = [b.strip() for b in brands.split(',') if len(b.strip()) > 2]
            # تحويل النص المستخرج لأحرف كبيرة لتسهيل البحث
            upper_text = all_text.upper()
            
            for brand in brand_list:
                if brand.upper() in upper_text:
                    found_brands.add(brand)

        # 6. إرجاع النتيجة
        return {
            "success": True,
            "codes": list(unique_codes),
            "brands": list(found_brands),
            "count_codes": len(unique_codes),
            "count_brands": len(found_brands)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

# لتشغيل السيرفر محلياً (للتجربة فقط)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
