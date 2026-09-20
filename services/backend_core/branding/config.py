from pydantic import BaseModel

class Branding(BaseModel):
    company_name_ar: str = "شركة هائل سعيد أنعم وشركاه"
    company_name_en: str = "Hayel Saeed Anam & Co."
    platform_name: str = "HSAAI"
    ownership_scope: str = "Internal enterprise AI platform"
    primary_color: str = "#F0CF3A"
    secondary_color: str = "#050505"
    internal_only: bool = True
    logo_asset: str = "/brand/hsa-logo.jpg"

branding = Branding()
