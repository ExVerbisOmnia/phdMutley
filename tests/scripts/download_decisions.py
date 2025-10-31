#!/usr/bin/env python3
"""
PDF Download Script for Climate Litigation Database
Downloads decision PDFs from URLs in the database and organizes them by geography.
"""

import pandas as pd
import requests
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import logging

# Configure logging to track download progress and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_log.txt'),
        logging.StreamHandler()
    ]
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# -------------------- TEST MODE CONFIGURATION --------------------
# Set to True to enable test mode (process limited rows)
# Set to False to process the entire database
TEST_MODE = True

# Number of rows to process in test mode
TEST_N_ROWS = 15

# Test mode strategy - choose one:
# 'first'   : Process the first N rows
# 'range'   : Process a specific range of rows (set TEST_RANGE_START and TEST_RANGE_END)
# 'random'  : Process N random rows from the database
TEST_STRATEGY = 'first'

# Only used when TEST_STRATEGY = 'range'
TEST_RANGE_START = 0    # Starting row index (0-based)
TEST_RANGE_END = 15     # Ending row index (exclusive)
# -----------------------------------------------------------------

# Path to the Excel database file
DATABASE_FILE = 'phdMutley/pdfs/downloaded'

# Base directory where all geography folders will be created
BASE_OUTPUT_DIR = 'phdMutley/pdfs/downloaded'

# Column names from the database
CASE_ID_COLUMN = 'Case ID'
URL_COLUMN = 'Document Content URL'
GEOGRAPHY_COLUMN = 'Geography ISOs'

# Download settings
REQUEST_TIMEOUT = 30  # Timeout for each download request (seconds)
RETRY_ATTEMPTS = 3    # Number of retry attempts for failed downloads
DELAY_BETWEEN_DOWNLOADS = 0.5  # Delay between downloads to avoid overwhelming server

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def sanitize_filename(filename):
    """
    Sanitize a filename by removing or replacing invalid characters.
    
    Args:
        filename (str): The filename to sanitize
        
    Returns:
        str: Sanitized filename safe for use in file systems
    """
    # Replace characters that are problematic in filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def create_directory_if_not_exists(directory_path):
    """
    Create a directory if it doesn't already exist.
    
    Args:
        directory_path (str or Path): Path to the directory to create
        
    Returns:
        Path: Path object of the created/existing directory
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    logging.info(f"Directory ready: {path}")
    return path


def download_file(url, output_path, retry_count=0):
    """
    Download a file from a URL and save it to the specified path.
    
    Args:
        url (str): URL of the file to download
        output_path (Path): Path where the file should be saved
        retry_count (int): Current retry attempt number
        
    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Make the HTTP GET request
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Check if the content type suggests it's a PDF or document
        content_type = response.headers.get('content-type', '').lower()
        
        # Write the content to file in chunks to handle large files
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
        
        # Log content type information for non-PDF files
        if 'pdf' not in content_type and content_type:
            logging.warning(f"Downloaded file may not be PDF (content-type: {content_type}): {output_path.name}")
        
        logging.info(f"Successfully downloaded: {output_path.name}")
        return True
        
    except requests.exceptions.RequestException as e:
        # Handle download errors with retry logic
        if retry_count < RETRY_ATTEMPTS:
            logging.warning(f"Download failed (attempt {retry_count + 1}/{RETRY_ATTEMPTS}): {url}")
            logging.warning(f"Error: {str(e)}")
            time.sleep(2 ** retry_count)  # Exponential backoff
            return download_file(url, output_path, retry_count + 1)
        else:
            logging.error(f"Failed to download after {RETRY_ATTEMPTS} attempts: {url}")
            logging.error(f"Error: {str(e)}")
            return False
    except Exception as e:
        logging.error(f"Unexpected error downloading {url}: {str(e)}")
        return False


def process_database(database_path):
    """
    Main function to process the database and download all PDFs.
    
    Args:
        database_path (str): Path to the Excel database file
        
    Returns:
        dict: Statistics about the download process
    """
    # Initialize statistics counters
    stats = {
        'total_rows': 0,
        'successful_downloads': 0,
        'failed_downloads': 0,
        'skipped_no_url': 0,
        'skipped_no_case_id': 0,
        'skipped_no_geography': 0
    }
    
    # Read the Excel database
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
        logging.info(f"TEST MODE ENABLED - Strategy: '{TEST_STRATEGY}' with N={TEST_N_ROWS}")
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
            # Process N random rows (use local variable to avoid modifying global)
            n_rows = TEST_N_ROWS
            if n_rows > len(df):
                logging.warning(f"TEST_N_ROWS ({n_rows}) exceeds database size ({len(df)}). Using all rows.")
                n_rows = len(df)
            df = df.sample(n=n_rows, random_state=42)  # random_state for reproducibility
            df = df.sort_index()  # Sort by original index for easier tracking
            logging.info(f"Processing {n_rows} random rows")
            logging.info(f"Selected row indices: {sorted(df.index.tolist())}")
            
        else:
            logging.error(f"Invalid TEST_STRATEGY: '{TEST_STRATEGY}'. Using first {TEST_N_ROWS} rows.")
            df = df.head(TEST_N_ROWS)
    
    # Update statistics with the actual number of rows to process
    stats['total_rows'] = len(df)
    logging.info(f"Rows to process: {stats['total_rows']}\n")
    
    # Create base output directory
    base_path = create_directory_if_not_exists(BASE_OUTPUT_DIR)
    
    # Track which geography folders have been created
    created_folders = set()
    
    # Iterate through each row in the database
    for idx, row in df.iterrows():
        # Extract relevant data from the current row
        case_id = row.get(CASE_ID_COLUMN)
        url = row.get(URL_COLUMN)
        geography = row.get(GEOGRAPHY_COLUMN)
        
        # Log progress every 100 rows
        if (idx + 1) % 100 == 0:
            logging.info(f"Progress: {idx + 1}/{stats['total_rows']} rows processed")
        
        # Validate that all required fields are present
        if pd.isna(case_id) or not case_id:
            logging.warning(f"Row {idx + 1}: Missing Case ID, skipping")
            stats['skipped_no_case_id'] += 1
            continue
            
        if pd.isna(url) or not url:
            logging.warning(f"Row {idx + 1}: Missing URL for Case ID '{case_id}', skipping")
            stats['skipped_no_url'] += 1
            continue
            
        if pd.isna(geography) or not geography:
            logging.warning(f"Row {idx + 1}: Missing Geography for Case ID '{case_id}', skipping")
            stats['skipped_no_geography'] += 1
            continue
        
        # Sanitize geography name for use as folder name
        geography_folder = sanitize_filename(str(geography).strip())
        
        # Create geography-specific folder if it doesn't exist yet
        if geography_folder not in created_folders:
            geography_path = base_path / geography_folder
            create_directory_if_not_exists(geography_path)
            created_folders.add(geography_folder)
        
        # Construct the output file path
        geography_path = base_path / geography_folder
        filename = f"decision-{sanitize_filename(str(case_id))}.pdf"
        output_path = geography_path / filename
        
        # Check if file already exists (to avoid re-downloading)
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
        time.sleep(DELAY_BETWEEN_DOWNLOADS)
    
    return stats


def print_summary(stats):
    """
    Print a summary of the download process statistics.
    
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
    logging.info(f"Skipped (no Geography):      {stats['skipped_no_geography']}")
    logging.info("="*70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    logging.info("="*70)
    logging.info("PDF DOWNLOAD SCRIPT FOR CLIMATE LITIGATION DATABASE")
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
        logging.info(f"\n✓  FULL MODE: Processing entire database")
    
    logging.info("="*70 + "\n")
    
    # Check if database file exists
    if not os.path.exists(DATABASE_FILE):
        logging.error(f"Database file not found: {DATABASE_FILE}")
        logging.error("Please ensure the file is in the same directory as this script.")
        exit(1)
    
    # Process the database and download all PDFs
    stats = process_database(DATABASE_FILE)
    
    # Print final summary
    print_summary(stats)
    
    if TEST_MODE:
        logging.info("\n⚠️  TEST MODE was enabled. To process the full database:")
        logging.info("   Set TEST_MODE = False in the configuration section")
    
    logging.info("\nDownload process completed!")
