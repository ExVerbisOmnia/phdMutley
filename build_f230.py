import json

data = {
  "document_id": "f230a3a6-5207-5630-877c-253919398b62",
  "case_id": "48cc4fec-eb56-547d-a687-bfd275984121",
  "source_jurisdiction": "United States Court of Appeals for the District of Columbia (D.C. Cir.)",
  "source_region": "Global North",
  "source_year": 2018,
  "verification_timestamp": "2026-05-14T00:00:00Z",
  "total_citations_extracted": 5,
  "total_confirmed": 5,
  "total_not_found": 0,
  "total_misattributed": 0,
  "total_not_a_case": 0,
  "total_duplicates": 0,
  "unique_citations_confirmed": 5
}
print(json.dumps(data))
