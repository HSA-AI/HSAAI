def route_agent(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in ["راتب", "موظف", "توظيف", "اجازة", "إجازة", "hr", "employee", "leave", "recruitment"]):
        return "hr"
    if any(k in msg for k in ["ميزانية", "فاتورة", "مصروف", "مشتريات", "finance", "budget", "invoice", "payment"]):
        return "finance"
    if any(k in msg for k in ["مدير", "تقرير", "تنفيذي", "استراتيجية", "مؤشر", "مؤشرات", "executive", "kpi", "strategy"]):
        return "executive"
    if any(k in msg for k in ["ملف", "وثيقة", "مستند", "مصدر", "سياسة", "لائحة", "document", "rag", "search", "policy"]):
        return "rag"
    if any(k in msg for k in ["دعم", "تقني", "كلمة المرور", "حساب", "شبكة", "نظام", "it", "ticket", "password", "access"]):
        return "it"
    return "general"
