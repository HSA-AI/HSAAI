/**
 * HSAAI Brand Constants — aligned with the official design reference (index.html)
 */
export const brand = {
  companyNameAr: "مجموعة هائل سعيد أنعم",
  companyNameEn: "Hayel Saeed Anam Group",
  platformName: "HSAAI",
  platformFullNameEn: "Hayel Saeed Anam Artificial Intelligence Platform",
  platformFullNameAr: "منصة التشغيل الذكي المؤسسية",
  platformSubtitleAr: "منصة التشغيل الذكي المؤسسية — HSA Group",
  taglineEn: "ENTERPRISE AI PLATFORM",
  // FIX: serve from /brand/* (public middleware path) so the official logo
  // renders on the unauthenticated login page. Original root-level path was
  // behind auth and always failed on /login.
  logoPath: "/brand/hsaai_official_logo.png",
  legacyLogoPath: "/brand/hsa-logo.jpg",
  assistant: {
    name: "HSAAI Assistant",
    nameAr: "مساعد HSAAI المؤسسي",
    iconPath: "/brand/hsaai-assistant-circle.png",
    iconSvgPath: "/brand/hsaai-assistant-circle.svg",
    iconWebpPath: "/brand/hsaai-assistant-circle.webp",
    descriptionAr: "أيقونة دائرية رسمية للمساعد الذكي الداخلي تظهر لجميع الموظفين للاستفسار السريع داخل المنصة.",
    quickPrompts: [
      "ما سياسة الإجازات؟",
      "ابحث في مستندات المؤسسة",
      "افتح لي مساعدة تقنية",
      "لخص آخر تقرير متاح"
    ]
  },
  /** Official palette — single source of truth mirrors tailwind.config.ts */
  colors: {
    gold: "#F4C430",
    goldDark: "#A67C00",
    goldSoft: "#FDF4E3",
    black: "#111111",
    blackSoft: "#1A1A1A",
    bg: "#FAFAF9",
    white: "#FFFFFF",
    border: "#E7E5E4",
    textSecondary: "#64748B",
  },
  /** Platform stats — from the official design reference (index.html) */
  stats: [
    { value: 14, labelAr: "خدمة", labelEn: "Services" },
    { value: 36, labelAr: "حاوية Docker", labelEn: "Docker Containers" },
    { value: 21, labelAr: "وكيل ذكاء", labelEn: "AI Agents" },
    { value: 142, labelAr: "فحص ناجح", labelEn: "Passed Checks" },
  ],
  footer: {
    line1Ar: "HSAAI — Hayel Saeed Anam Artificial Intelligence Platform",
    line2Ar: "منصة ذكاء اصطناعي مؤسسية — مجموعة هائل سعيد أنعم",
    copyright: "الشعار محفوظ © HSA Group · Information Technology",
  },
} as const;
