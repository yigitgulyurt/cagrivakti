
from app.factory import create_app
from app.extensions import db
from app.models import NamazVakti
from datetime import date

app = create_app()

with app.app_context():
    # Feb 11
    vakit_11 = NamazVakti.query.filter_by(sehir='Istanbul', tarih=date(2026, 2, 11)).first()
    print(f"--- Data for Feb 11, 2026 ---")
    if vakit_11:
        print(f"Imsak: {vakit_11.imsak}")
        print(f"Gunes: {vakit_11.gunes}")
        print(f"Ogle: {vakit_11.ogle}")
        print(f"Ikindi: {vakit_11.ikindi}")
        print(f"Aksam: {vakit_11.aksam}")
        print(f"Yatsi: {vakit_11.yatsi}")
    else:
        print("No data found for Feb 11")
