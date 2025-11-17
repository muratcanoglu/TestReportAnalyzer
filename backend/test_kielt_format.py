# -*- coding: utf-8 -*-
from pdf_format_detector import detect_pdf_format, parse_kielt_format, extract_measurement_params

# GERÇEK PDF text'i (kullanıcının gönderdiği)
pdf_text = """
Test Koşulları
No:1 , NOSAB 16140 Bursa Anwesende : Herr Berberich, Herrmann, Heider
Versuchsbedingungen : ECE-R 80, M3/M2 Test conditions
Justierung/Kontrolle : A. HAC, [120.1, 146.05 ms] 161.18 HAC, [110.65, 116.9 ms] 283.27
a Kopf über 3 ms [g] 58.15
a Kopf über 3 ms [g] 64.72
ThAC [g] 18.4
ThAC [g] 18.27
FAC right F [kN] 4.40
FAC right F [kN] 5.94
FAC left F [kN] 4.82
FAC left F [kN] 6.34

Schlittenverzögerung: Examiner: IWW Test conditions: UN-R80
Date: 11.02.2022 Test vehicle: MAN LE MU 6
"""

print("="*70)
print("GERÇEK PDF FORMATINI TEST EDİYORUZ")
print("="*70)

# 1. Format tespit
print("\n[1] Format Tespit")
format_type = detect_pdf_format(pdf_text)
print(f"Format: {format_type}")
assert format_type == 'kielt_format', "Format tespit edilemedi!"

# 2. Parse
print("\n[2] Bölüm Parse")
sections = parse_kielt_format(pdf_text)
for key, value in sections.items():
    print(f"\n{key}:")
    print(f"  Uzunluk: {len(value)} karakter")
    print(f"  İçerik: {value[:100]}...")

# 3. Measurement params
print("\n[3] Measurement Params")
params = extract_measurement_params(pdf_text)
print(f"Toplam {len(params)} ölçüm kaydı bulundu:")

for param in params:
    print(
        f"\n  {param['name']} [{param['unit']}]: {param['value']} (raw={param['raw']})"
    )

# Kontrol
print("\n" + "="*70)
print("KONTROL")
print("="*70)

expected_params = [
    'Baş ivmesi',
    'Göğüs ivmesi',
    'Sağ femur',
    'Sol femur',
    'HAC'
]

found_params = sorted({p['name'] for p in params})
print(f"\nBeklenen: {expected_params}")
print(f"Bulunan: {found_params}")

if all(name in found_params for name in expected_params):
    print("\n✓ TEST BAŞARILI - Measurement params bulundu!")
else:
    print("\n✗ TEST BAŞARISIZ - Yeterli parametre bulunamadı!")
