
from app.factory import create_app
from app.services import DiniGunlerService

app = create_app()

with app.app_context():
    print("--- Test Dini Günler ---")
    gunler = DiniGunlerService.get_dini_gunler()
    for gun in gunler:
        tarih_str = DiniGunlerService.format_turkish_date(gun['tarih'])
        print(f"{gun['ad']}: {tarih_str} (kalan: {gun['kalan_gun']} gün)")
