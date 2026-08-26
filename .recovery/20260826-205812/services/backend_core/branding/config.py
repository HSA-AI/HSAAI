from pydantic import BaseModel

class Branding(BaseModel):
    company_name_ar: str = "شركة هائل سعيد أنعم وشركاه"
    company_name_en: str = "Hayel Saeed Anam & Co."
    platform_name: str = "HSAAI"
    ownership_scope: str = "Internal enterprise AI platform"
    primary_color: str = "#F4C430"
    secondary_color: str = "#A67C00"
    accent_color: str = "#111111"
    background_color: str = "#FFFFFF"
    internal_only: bool = True
    logo_asset: str = "/brand/hsa-logo.png"

branding = Branding()
