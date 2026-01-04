from medicosdoc_scraper import MedicosDocScraper, _normalize_text


BASE_URL = "https://medicosdoc.com/en/medical-directory-colombia"


def test_filter_gynecologist_first_page():
    scraper = MedicosDocScraper()
    doctors = list(scraper.fetch_doctors(BASE_URL, max_pages=2))
    filtered = scraper.filter_by_specialty(doctors, "Gynecologist")
    assert filtered, "Expected gynecologists in sample pages"

    records = [scraper.to_record(doc, BASE_URL) for doc in filtered]
    for record in records:
        specialty = _normalize_text(record["specialty"])
        assert "gynecolog" in specialty
        assert record["name"]


def test_to_record_shapes_output():
    scraper = MedicosDocScraper()
    doctors = list(scraper.fetch_doctors(BASE_URL, max_pages=1))
    assert doctors, "Expected at least one doctor on the first page"

    record = scraper.to_record(doctors[0], BASE_URL)
    expected_keys = {
        "id",
        "name",
        "specialty",
        "city",
        "address",
        "medical_center",
        "office",
        "highlighted_services",
        "consult_value",
        "premium",
        "rating_average",
        "rating_count",
        "photo_url",
    }
    assert expected_keys.issubset(record.keys())
