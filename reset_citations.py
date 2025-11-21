from sqlalchemy import create_engine, text
from config import DB_CONFIG
from sqlalchemy.engine import URL

# Connect
url = URL.create(**DB_CONFIG)
engine = create_engine(url)

with engine.connect() as conn:
    print("Clearing old citation data...")
    # CASCADE ensures it also clears the linked 'citations' table
    conn.execute(text("TRUNCATE citation_extractions CASCADE;"))
    conn.commit()
    print("Done! You can now re-run the extraction script.")