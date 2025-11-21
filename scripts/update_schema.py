"""
Script to update database schema - add document_id to citations table.

INPUT: Existing PostgreSQL database connection
ALGORITHM: Execute ALTER TABLE commands to add document_id column and constraints
OUTPUT: Updated citations table schema
"""

import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'database': 'climate_litigation',
    'user': 'phdmutley',
    'password': '197230'  # Substitua pela sua senha
}


def execute_schema_update():
    """
    Execute schema updates on citations table.
    
    ALGORITHM:
        1. Connect to database
        2. Execute ALTER TABLE to add column
        3. Add foreign key constraint
        4. Create index
        5. Commit or rollback on error
    
    OUTPUT: Success or error message
    """
    # SQL commands to execute
    sql_commands = [
        # Add document_id column
        """
        ALTER TABLE citations 
        ADD COLUMN document_id UUID;
        """,
        
        # Add foreign key constraint
        """
        ALTER TABLE citations
        ADD CONSTRAINT fk_citations_document
        FOREIGN KEY (document_id) 
        REFERENCES documents(document_id)
        ON DELETE CASCADE;
        """,
        
        # Create index for performance
        """
        CREATE INDEX idx_citations_document_id 
        ON citations(document_id);
        """
    ]
    
    conn = None
    
    try:
        # Connect to database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Execute each command
        for i, command in enumerate(sql_commands, 1):
            logger.info(f"Executing command {i}/{len(sql_commands)}...")
            cursor.execute(command)
            logger.info(f"✓ Command {i} executed successfully")
        
        # Commit changes
        conn.commit()
        logger.info("\n✓ All schema updates committed successfully!")
        
        # Verify the changes
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'citations'
            AND column_name = 'document_id';
        """)
        
        result = cursor.fetchone()
        if result:
            logger.info(f"\nVerification: Column 'document_id' exists")
            logger.info(f"  - Type: {result[1]}")
            logger.info(f"  - Nullable: {result[2]}")
        
        return True
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"\n✗ Error updating schema: {e}")
        logger.error(f"Error code: {e.pgcode}")
        logger.error(f"Error message: {e.pgerror}")
        return False
        
    finally:
        if conn:
            cursor.close()
            conn.close()
            logger.info("Database connection closed")


def check_if_column_exists():
    """
    Check if document_id column already exists.
    
    OUTPUT: Boolean indicating if column exists
    """
    conn = None
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'citations' 
                AND column_name = 'document_id'
            );
        """)
        
        exists = cursor.fetchone()[0]
        return exists
        
    except psycopg2.Error as e:
        logger.error(f"Error checking column: {e}")
        return False
        
    finally:
        if conn:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("DATABASE SCHEMA UPDATE - Add document_id to citations")
    logger.info("="*60)
    
    # Check if column already exists
    logger.info("\nChecking if document_id column already exists...")
    if check_if_column_exists():
        logger.warning("⚠ Column 'document_id' already exists in citations table!")
        logger.warning("Skipping schema update.")
    else:
        logger.info("Column does not exist. Proceeding with update...")
        
        # Execute schema update
        success = execute_schema_update()
        
        if success:
            logger.info("\n" + "="*60)
            logger.info("✓ SCHEMA UPDATE COMPLETED SUCCESSFULLY")
            logger.info("="*60)
        else:
            logger.error("\n" + "="*60)
            logger.error("✗ SCHEMA UPDATE FAILED")
            logger.error("="*60)