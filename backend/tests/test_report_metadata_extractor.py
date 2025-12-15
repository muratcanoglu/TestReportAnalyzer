from backend.report_metadata_extractor import derive_report_metadata


def test_derive_report_metadata_prefers_structured_bezeichnung():
    structured = {
        "page_2_metadata": {
            "pruefling": {"bezeichnung": "Seri Koltuk A1", "typ": "Yedek"},
            "testfahrzeug": "Elektrikli Minibüs",
        }
    }

    page_texts = [
        "Kapak",  # page 1
        "Prüfling sayfası",  # page 2
        "Dummy – Belastung:\nBearbeiter: KIELT Lab",
        "Schlittenverzögerung:\nTest vehicle: Test Platform X",
    ]

    result = derive_report_metadata(structured, page_texts=page_texts)

    assert result["seat_model"] == "Seri Koltuk A1"
    assert result["lab_name"] == "KIELT Lab"
    assert result["vehicle_platform"] == "Test Platform X"


def test_derive_report_metadata_falls_back_to_page_2_vehicle():
    structured = {
        "page_2_metadata": {
            "pruefling": {"typ": "Koltuk Tipi"},
            "testfahrzeug": "Platform B",
        }
    }

    result = derive_report_metadata(structured, page_texts=["", "", "", ""])

    assert result["seat_model"] == "Koltuk Tipi"
    assert result["vehicle_platform"] == "Platform B"
