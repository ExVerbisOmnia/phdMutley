#!/usr/bin/env python3
"""
PDF Download Script for Climate Litigation Database (Version 2.0 - Async)
=========================================================================
Downloads decision PDFs from URLs in the database asynchronously.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/download_decisions_v2.py

This version uses asyncio and aiohttp to perform parallel downloads, 
drastically reducing the time required to process the full dataset.
"""

import sys
import os
import asyncio
import aiohttp
import aiofiles  # Requires: pip install aiofiles
import pandas as pd
import logging
import time
from pathlib import Path

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root to path to import config
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import CONFIG, PDF_DOWNLOAD_DIR, DATABASE_FILE, LOGS_DIR, TEST_CONFIG

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'download_log_async.txt'),
        logging.StreamHandler()
    ]
)

# ============================================================================
# ASYNC FUNCTIONS
# ============================================================================

def sanitize_filename(filename):
    """Clean a filename by removing invalid characters."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

async def download_file_async(session, url, output_path, semaphore):
    """
    Download a single file asynchronously with concurrency limits.
    """
    async with semaphore:  # Limits active downloads to CONFIG['CONCURRENT_DOWNLOADS']
        if output_path.exists():
            return 'exists'

        try:
            timeout = aiohttp.ClientTimeout(total=CONFIG['REQUEST_TIMEOUT'])
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                
                # content-type check (optional warning)
                ctype = response.headers.get('content-type', '').lower()
                if 'pdf' not in ctype and ctype:
                    logging.warning(f"⚠️ Content-Type not PDF ({ctype}): {output_path.name}")

                # Write file asynchronously
                content = await response.read()
                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(content)
                
                logging.info(f"✓ Downloaded: {output_path.name}")
                return 'success'

        except asyncio.TimeoutError:
            logging.error(f"✗ Timeout: {url}")
            return 'failed'
        except Exception as e:
            logging.error(f"✗ Failed {url}: {e}")
            return 'failed'

async def process_downloads_async(df):
    """
    Main async orchestrator: creates tasks and gathers results.
    """
    stats = {'success': 0, 'failed': 0, 'exists': 0, 'skipped': 0}
    
    # Semaphore controls how many downloads happen at ONCE
    semaphore = asyncio.Semaphore(CONFIG['CONCURRENT_DOWNLOADS'])
    
    # Create a single session for all requests (more efficient)
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        logging.info(f"Queuing tasks for {len(df)} documents...")
        
        for _, row in df.iterrows():
            doc_id = row.get('Document ID')
            url = row.get('Document Content URL')
            
            # Validation
            if pd.isna(doc_id) or pd.isna(url):
                stats['skipped'] += 1
                continue
            
            # Prepare path
            filename = f"doc_{sanitize_filename(str(doc_id))}.pdf"
            output_path = PDF_DOWNLOAD_DIR / filename
            
            # Create task (but don't await it yet)
            task = download_file_async(session, url, output_path, semaphore)
            tasks.append(task)
        
        # Run all tasks concurrently
        logging.info(f"Starting {len(tasks)} downloads with concurrency={CONFIG['CONCURRENT_DOWNLOADS']}...")
        results = await asyncio.gather(*tasks)
        
        # Tally results
        for r in results:
            stats[r] += 1
            
    return stats

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    
    logging.info("="*70)
    logging.info("PDF DOWNLOAD SCRIPT (ASYNC) - CLIMATE LITIGATION DATABASE")
    logging.info("="*70)
    
    # check directories
    if not os.path.exists(DATABASE_FILE):
        logging.error(f"Database file not found: {DATABASE_FILE}")
        sys.exit(1)
        
    # Load Data
    try:
        df = pd.read_excel(DATABASE_FILE)
        logging.info(f"Loaded database with {len(df)} rows.")
    except Exception as e:
        logging.error(f"Failed to read database: {e}")
        sys.exit(1)

    # Apply Test Mode
    if TEST_CONFIG['ENABLED']:
        limit = TEST_CONFIG['LIMIT']
        logging.info(f"\n⚠️  TEST MODE: Processing first {limit} rows only.")
        df = df.head(limit)
    
    # Run Async Process
    start_time = time.time()
    
    try:
        stats = asyncio.run(process_downloads_async(df))
    except KeyboardInterrupt:
        logging.info("\n🛑 Process interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"\n✗ Fatal error in async loop: {e}")
        sys.exit(1)
        
    duration = time.time() - start_time
    
    # Summary
    logging.info("\n" + "="*70)
    logging.info("DOWNLOAD SUMMARY")
    logging.info("="*70)
    logging.info(f"Total processed:     {len(df)}")
    logging.info(f"Successful:          {stats['success']}")
    logging.info(f"Already existed:     {stats['exists']}")
    logging.info(f"Failed:              {stats['failed']}")
    logging.info(f"Skipped (Metadata):  {stats['skipped']}")
    logging.info(f"Time elapsed:        {duration:.2f}s")
    logging.info("="*70)
    
    if TEST_CONFIG['ENABLED']:
        logging.info("\n⚠️  TEST MODE was enabled. Edit config.py to process full dataset.")