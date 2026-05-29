import json

data = {
  "document_id": "8371218c-54b1-5f43-8d76-74d386aa0abb",
  "case_id": "5a7c565f-dffb-56c1-a222-19a53f573bbb",
  "source_jurisdiction": "United States Federal Courts",
  "source_region": "Global North",
  "source_year": 2009,
  "verification_timestamp": "2026-05-14T00:00:00Z",
  "total_citations_extracted": 4,
  "total_confirmed": 4,
  "total_not_found": 0,
  "total_misattributed": 0,
  "total_not_a_case": 0,
  "total_duplicates": 0,
  "unique_citations_confirmed": 4,
  "citations": [],
  "summary": {}
}
print(json.dumps(data))