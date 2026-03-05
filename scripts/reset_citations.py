from sqlalchemy import text

from gcp_secrets import get_engine

# Connect
engine = get_engine()

with engine.connect() as conn:
    print("Clearing old citation data...")
    # Clear both detailed results and summary status
    conn.execute(
        text("TRUNCATE citation_extraction_phased, citation_extraction_phased_summary CASCADE;")
    )
    conn.commit()
    print("Done! Citation data and processing status have been reset.")
