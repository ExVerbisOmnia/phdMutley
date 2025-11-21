#!/usr/bin/env python3
"""
PDF Download Script for Climate Litigation Database (Version 2.0)
==================================================================
Downloads decision PDFs from URLs in the database to a single organized folder.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/download_decisions_v2.py

This version stores all PDFs in a single folder for easier text extraction processing.
"""

import pandas as pd
import requests
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import logging

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging to track download progress and errors
# Logs are written to both a file and displayed in the terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/download_log.txt'),  # Save logs to file
        logging.StreamHandler()  # Also display in terminal
    ]
)

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# -------------------- TEST MODE CONFIGURATION --------------------
# TEST MODE allows you to test the script on a small sample before processing all 2,900+ PDFs
# Set to True to enable test mode (process limited rows)
# Set to False to process the entire database
TEST_MODE = True

# Number of rows to process in test mode
TEST_N_ROWS = 15

# Test mode strategy - choose one:
# 'first'   : Process the first N rows from the database
# 'range'   : Process a specific range of rows (set TEST_RANGE_START and TEST_RANGE_END below)
# 'random'  : Process N random rows from the database (good for testing diversity)
TEST_STRATEGY = 'first'

# Only used when TEST_STRATEGY = 'range'
TEST_RANGE_START = 0    # Starting row index (0-based, so 0 means first row)
TEST_RANGE_END = 15     # Ending row index (exclusive, so 15 means up to row 14)
# -----------------------------------------------------------------

# Path to the Excel database file containing case information
# This file should have columns: 'Document ID', 'Case ID', 'Document Content URL', 'Geography ISOs'
DATABASE_FILE = 'baseDecisions.xlsx'

# Base directory where all PDFs will be stored
# All PDFs will be saved to this single folder for easier processing
BASE_OUTPUT_DIR = 'scripts/phase1/pdfs/downloaded'

# Column names from the Excel database
# These must match the exact column names in your baseDecisions.xlsx file
DOCUMENT_ID_COLUMN = 'Document ID'  # Unique identifier for each document
CASE_ID_COLUMN = 'Case ID'
URL_COLUMN = 'Document Content URL'
GEOGRAPHY_COLUMN = 'Geography ISOs'

# Download settings
REQUEST_TIMEOUT = 30  # Timeout for each download request (seconds) - prevents hanging
RETRY_ATTEMPTS = 3    # Number of retry attempts for failed downloads
DELAY_BETWEEN_DOWNLOADS = 0.5  # Delay between downloads in seconds (be respectful to server)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def sanitize_filename(filename):
    """
    Clean a filename by removing or replacing characters that aren't allowed in file systems.
    
    For example: "Case#123/456?" becomes "Case_123_456_"
    This prevents errors when trying to save files with invalid characters.
    
    Args:
        filename (str): The original filename that might contain invalid characters
        
    Returns:
        str: A cleaned filename that is safe to use in any file system
    """
    # These characters cause problems in Windows, Linux, or macOS file systems
    invalid_chars = '<>:"/\\|?*'
    
    # Replace each invalid character with an underscore
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    return filename


def create_directory_if_not_exists(directory_path):
    """
    Create a directory if it doesn't already exist.
    
    This function is "safe" - it won't fail if the directory already exists.
    It also creates any parent directories needed (e.g., if you specify
    'pdfs/downloaded' and 'pdfs' doesn't exist, it creates both).
    
    Args:
        directory_path (str or Path): Path to the directory to create
        
    Returns:
        Path: Path object of the created/existing directory
    """
    # Convert string path to Path object for better path handling
    path = Path(directory_path)
    
    # Create the directory and any parent directories needed
    # exist_ok=True means "don't fail if directory already exists"
    path.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Directory ready: {path}")
    return path


def download_file(url, output_path, retry_count=0):
    """
    Download a file from a URL and save it to the specified path.
    
    This function includes:
    - Retry logic (tries up to 3 times if download fails)
    - Exponential backoff (waits longer between each retry)
    - Content type validation (warns if file doesn't appear to be a PDF)
    - Chunk-based downloading (handles large files efficiently)
    
    Args:
        url (str): URL of the file to download
        output_path (Path): Path where the file should be saved
        retry_count (int): Current retry attempt number (used internally for recursion)
        
    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        # Set headers to make the request look like it's coming from a browser
        # Some servers block requests that don't have a User-Agent header
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Make the HTTP GET request to download the file
        # stream=True means we download in chunks rather than loading entire file in memory
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=True)
        
        # Check if the request was successful (status code 200)
        # raise_for_status() will raise an exception for 4xx or 5xx status codes
        response.raise_for_status()
        
        # Check what type of content the server says it's sending
        content_type = response.headers.get('content-type', '').lower()
        
        # Write the downloaded content to file in chunks
        # This approach is memory-efficient for large files
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                if chunk:  # Filter out keep-alive chunks (empty chunks)
                    f.write(chunk)
        
        # Warn if the file doesn't appear to be a PDF
        # (sometimes servers return HTML error pages instead)
        if 'pdf' not in content_type and content_type:
            logging.warning(f"Downloaded file may not be PDF (content-type: {content_type}): {output_path.name}")
        
        logging.info(f"Successfully downloaded: {output_path.name}")
        return True
        
    except requests.exceptions.RequestException as e:
        # Handle network-related errors (connection failed, timeout, etc.)
        
        # If we haven't exhausted all retry attempts, try again
        if retry_count < RETRY_ATTEMPTS:
            logging.warning(f"Download failed (attempt {retry_count + 1}/{RETRY_ATTEMPTS}): {url}")
            logging.warning(f"Error: {str(e)}")
            
            # Exponential backoff: wait 1s, then 2s, then 4s before retrying
            time.sleep(2 ** retry_count)
            
            # Recursively call this function to retry the download
            return download_file(url, output_path, retry_count + 1)
        else:
            # We've tried RETRY_ATTEMPTS times and failed each time
            logging.error(f"Failed to download after {RETRY_ATTEMPTS} attempts: {url}")
            logging.error(f"Error: {str(e)}")
            return False
            
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"Unexpected error downloading {url}: {str(e)}")
        return False


def process_database(database_path):
    """
    Main function to process the database and download all PDFs to a single folder.
    
    This function:
    1. Reads the Excel database
    2. Applies test mode filtering if enabled
    3. Creates the output directory
    4. Iterates through each row and downloads PDFs
    5. Tracks statistics about successes and failures
    
    Args:
        database_path (str): Path to the Excel database file (baseCompleta.xlsx)
        
    Returns:
        dict: Statistics about the download process including:
              - total_rows: Total number of rows processed
              - successful_downloads: Number of successfully downloaded PDFs
              - failed_downloads: Number of failed download attempts
              - skipped_no_url: Number of rows without URLs
              - skipped_no_case_id: Number of rows without Case IDs
    """
    # Initialize statistics counters
    # These track how the download process went
    stats = {
        'total_rows': 0,
        'successful_downloads': 0,
        'failed_downloads': 0,
        'skipped_no_url': 0,
        'skipped_no_case_id': 0,
    }
    
    # Read the Excel database into a pandas DataFrame
    logging.info(f"Reading database from: {database_path}")
    try:
        df = pd.read_excel(database_path)
        original_row_count = len(df)
        logging.info(f"Database loaded successfully. Total rows in database: {original_row_count}")
    except Exception as e:
        logging.error(f"Failed to read database: {str(e)}")
        return stats
    
    # Apply test mode filtering if enabled
    if TEST_MODE:
        logging.info(f"\n{'='*70}")
        logging.info(f"⚠️  TEST MODE ENABLED - Strategy: '{TEST_STRATEGY}' with N={TEST_N_ROWS}")
        logging.info(f"{'='*70}\n")
        
        if TEST_STRATEGY == 'first':
            # Process only the first N rows
            df = df.head(TEST_N_ROWS)
            logging.info(f"Processing first {TEST_N_ROWS} rows (rows 0 to {TEST_N_ROWS-1})")
            
        elif TEST_STRATEGY == 'range':
            # Process a specific range of rows
            df = df.iloc[TEST_RANGE_START:TEST_RANGE_END]
            logging.info(f"Processing rows {TEST_RANGE_START} to {TEST_RANGE_END-1} (total: {len(df)} rows)")
            
        elif TEST_STRATEGY == 'random':
            # Process N random rows (for testing diversity of documents)
            n_rows = TEST_N_ROWS
            if n_rows > len(df):
                logging.warning(f"TEST_N_ROWS ({n_rows}) exceeds database size ({len(df)}). Using all rows.")
                n_rows = len(df)
            
            # random_state=42 ensures reproducibility (same "random" selection each time)
            df = df.sample(n=n_rows, random_state=42)
            df = df.sort_index()  # Sort by original index for easier tracking
            logging.info(f"Processing {n_rows} random rows")
            logging.info(f"Selected row indices: {sorted(df.index.tolist())}")
            
        else:
            logging.error(f"Invalid TEST_STRATEGY: '{TEST_STRATEGY}'. Using first {TEST_N_ROWS} rows.")
            df = df.head(TEST_N_ROWS)
    
    # Update statistics with the actual number of rows to process
    stats['total_rows'] = len(df)
    logging.info(f"Rows to process: {stats['total_rows']}\n")
    
    # Create the output directory (single folder for all PDFs)
    base_path = create_directory_if_not_exists(BASE_OUTPUT_DIR)
    
    # Iterate through each row in the database
    for idx, row in df.iterrows():
        # Extract relevant data from the current row
        document_id = row.get(DOCUMENT_ID_COLUMN)
        case_id = row.get(CASE_ID_COLUMN)
        url = row.get(URL_COLUMN)

        # Log progress every 100 rows (so we know the script is still running)
        if (idx + 1) % 100 == 0:
            logging.info(f"Progress: {idx + 1}/{stats['total_rows']} rows processed")

        # Validate that required fields are present
        if pd.isna(document_id) or not document_id:
            logging.warning(f"Row {idx + 1}: Missing Document ID for Case ID '{case_id}', skipping")
            stats['skipped_no_case_id'] += 1
            continue

        if pd.isna(url) or not url:
            logging.warning(f"Row {idx + 1}: Missing URL for Document ID '{document_id}', skipping")
            stats['skipped_no_url'] += 1
            continue

        # Create the filename using the Document ID (unique per document)
        # Format: "doc_{document_id}.pdf" (e.g., "doc_12345.pdf")
        filename = f"doc_{sanitize_filename(str(document_id))}.pdf"
        output_path = base_path / filename
        
        # Check if file already exists (to avoid re-downloading)
        # This is useful if the script crashes and you need to restart it
        if output_path.exists():
            logging.info(f"File already exists, skipping: {filename}")
            stats['successful_downloads'] += 1  # Count as successful since file is already there
            continue
        
        # Download the file
        logging.info(f"Downloading [{idx + 1}/{stats['total_rows']}]: {filename}")
        success = download_file(url, output_path)
        
        # Update statistics based on download result
        if success:
            stats['successful_downloads'] += 1
        else:
            stats['failed_downloads'] += 1
        
        # Add a small delay between downloads to be respectful to the server
        # This prevents overwhelming the server with too many rapid requests
        time.sleep(DELAY_BETWEEN_DOWNLOADS)
    
    return stats


def print_summary(stats):
    """
    Print a summary of the download process statistics.
    
    This provides a clear overview of how the download process went,
    showing successes, failures, and reasons for skipped files.
    
    Args:
        stats (dict): Dictionary containing download statistics
    """
    logging.info("\n" + "="*70)
    logging.info("DOWNLOAD SUMMARY")
    logging.info("="*70)
    logging.info(f"Total rows processed:        {stats['total_rows']}")
    logging.info(f"Successful downloads:        {stats['successful_downloads']}")
    logging.info(f"Failed downloads:            {stats['failed_downloads']}")
    logging.info(f"Skipped (no URL):            {stats['skipped_no_url']}")
    logging.info(f"Skipped (no Case ID):        {stats['skipped_no_case_id']}")
    
    # Calculate success rate
    if stats['total_rows'] > 0:
        success_rate = (stats['successful_downloads'] / stats['total_rows']) * 100
        logging.info(f"Success rate:                {success_rate:.1f}%")
    
    logging.info("="*70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when you execute the script directly:
    python download_decisions_v2.py
    """
    
    # Check if we're in the correct directory
    if not os.path.exists(DATABASE_FILE):
        logging.error(f"✗ Database file not found: {DATABASE_FILE}")
        logging.error(f"✗ Current directory: {os.getcwd()}")
        logging.error("\n📁 You must run this script from the project root directory:")
        logging.error("   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley")
        logging.error("   python scripts/phase1/download_decisions_v2.py")
        exit(1)
    
    logging.info("="*70)
    logging.info("PDF DOWNLOAD SCRIPT - CLIMATE LITIGATION DATABASE v2.0")
    logging.info("="*70)
    logging.info(f"Database file: {DATABASE_FILE}")
    logging.info(f"Output directory: {BASE_OUTPUT_DIR}")
    
    # Display test mode status
    if TEST_MODE:
        logging.info(f"\n⚠️  TEST MODE: ENABLED")
        logging.info(f"   Strategy: {TEST_STRATEGY}")
        logging.info(f"   N rows: {TEST_N_ROWS}")
        if TEST_STRATEGY == 'range':
            logging.info(f"   Range: rows {TEST_RANGE_START} to {TEST_RANGE_END-1}")
    else:
        logging.info(f"\n✅ FULL MODE: Processing entire database")
    
    logging.info("="*70 + "\n")
    
    # Create logs directory if it doesn't exist
    create_directory_if_not_exists('logs')
    
    # Process the database and download all PDFs
    stats = process_database(DATABASE_FILE)
    
    # Print final summary
    print_summary(stats)
    
    if TEST_MODE:
        logging.info("\n⚠️  TEST MODE was enabled. To process the full database:")
        logging.info("   Set TEST_MODE = False in the configuration section")
    
    logging.info("\nDownload process completed!")
    logging.info(f"PDFs saved to: {BASE_OUTPUT_DIR}")
