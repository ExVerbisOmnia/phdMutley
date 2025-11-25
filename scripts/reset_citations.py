from sqlalchemy import create_engine, text
from config import DB_CONFIG
from sqlalchemy.engine import URL

# Connect
url = URL.create(**DB_CONFIG)
engine = create_engine(url)

with engine.connect() as conn:
    print("Clearing old citation data...")
    # Clear both detailed results and summary status
    conn.execute(text("TRUNCATE citation_extraction_phased, citation_extraction_phased_summary CASCADE;"))
    conn.commit()
    print("Done! Citation data and processing status have been reset.")