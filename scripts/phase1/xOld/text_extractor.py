"""
Text Extraction Module for Climate Litigation PhD Project
==========================================================

This module provides functions to extract text from PDF documents (court decisions)
and assess the quality of the extraction. It's designed specifically for the
climate litigation citation analysis project.

Key Features:
- Multi-library support (pdfplumber, PyPDF2, PyMuPDF) with automatic fallback
- Quality assessment of extracted text
- Scanned PDF detection
- Metadata extraction
- Comprehensive error handling

Author: Lucas Biasetton (Gus)
Project: Doutorado PM - Climate Litigation Citation Analysis
Version: 1.0
Date: October 31, 2025
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import re

# PDF processing libraries
# pdfplumber is the primary library due to superior quality for legal documents
import pdfplumber
import PyPDF2
import fitz  # PyMuPDF


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging for this module
# This creates a logger specific to text extraction operations
logger = logging.getLogger(__name__)


# ============================================================================
# PRIMARY EXTRACTION FUNCTION
# ============================================================================

def extract_text_from_pdf(
    pdf_path: str,
    method: str = 'auto'
) -> Dict[str, any]:
    """
    Extract text from a PDF file using the specified method.
    
    This is the main function for extracting text from court decision PDFs.
    It can use different libraries depending on the 'method' parameter,
    and automatically falls back to other methods if the primary one fails.
    
    Args:
        pdf_path (str): Full path to the PDF file to extract text from
        method (str): Extraction method to use. Options:
            - 'auto': Try libraries in order of quality (pdfplumber → PyMuPDF → PyPDF2)
            - 'pdfplumber': Use pdfplumber only (recommended for quality)
            - 'pymupdf': Use PyMuPDF/fitz only (faster but may miss layout)
            - 'pypdf2': Use PyPDF2 only (fastest but lowest quality)
    
    Returns:
        dict: A dictionary containing extraction results with the following keys:
            - text (str): The extracted text content
            - method_used (str): Which library successfully extracted the text
            - page_count (int): Number of pages in the PDF
            - word_count (int): Approximate number of words extracted
            - character_count (int): Number of characters in extracted text
            - quality (str): Quality assessment ("excellent", "good", "fair", "poor", "failed")
            - is_scanned (bool): Whether the PDF appears to be scanned (needs OCR)
            - errors (list): List of any errors or warnings encountered
            - extraction_duration_seconds (float): Time taken to extract text
    
    Example:
        >>> result = extract_text_from_pdf('/path/to/decision.pdf')
        >>> print(f"Extracted {result['word_count']} words using {result['method_used']}")
        >>> print(f"Quality: {result['quality']}")
    """
    # Initialize the result dictionary with default values
    result = {
        'text': '',
        'method_used': None,
        'page_count': 0,
        'word_count': 0,
        'character_count': 0,
        'quality': 'failed',
        'is_scanned': False,
        'errors': [],
        'extraction_duration_seconds': 0.0
    }
    
    # Record start time to measure extraction performance
    start_time = datetime.now()
    
    # Verify that the PDF file exists before attempting extraction
    if not os.path.exists(pdf_path):
        error_msg = f"PDF file not found: {pdf_path}"
        logger.error(error_msg)
        result['errors'].append(error_msg)
        return result
    
    # Verify that the file is actually a PDF (basic check)
    if not pdf_path.lower().endswith('.pdf'):
        error_msg = f"File does not appear to be a PDF: {pdf_path}"
        logger.warning(error_msg)
        result['errors'].append(error_msg)
    
    # Define the extraction attempt order based on the method parameter
    # This determines which library to try and in what order
    if method == 'auto':
        # Auto mode: try in order of quality (best to worst)
        # pdfplumber is best for legal docs but slowest
        # PyMuPDF is fast and good quality
        # PyPDF2 is fastest but lowest quality
        extraction_order = ['pdfplumber', 'pymupdf', 'pypdf2']
    elif method in ['pdfplumber', 'pymupdf', 'pypdf2']:
        # Specific method requested: only try that one
        extraction_order = [method]
    else:
        # Invalid method specified
        error_msg = f"Invalid extraction method: {method}. Using 'auto' instead."
        logger.warning(error_msg)
        result['errors'].append(error_msg)
        extraction_order = ['pdfplumber', 'pymupdf', 'pypdf2']
    
    # Try each extraction method in the defined order
    # Stop as soon as one succeeds
    for current_method in extraction_order:
        try:
            logger.info(f"Attempting extraction with {current_method}: {pdf_path}")
            
            # Call the appropriate extraction function based on the method
            if current_method == 'pdfplumber':
                text, page_count = _extract_with_pdfplumber(pdf_path)
            elif current_method == 'pymupdf':
                text, page_count = _extract_with_pymupdf(pdf_path)
            elif current_method == 'pypdf2':
                text, page_count = _extract_with_pypdf2(pdf_path)
            else:
                continue  # Skip unknown methods
            
            # If we got here, extraction succeeded
            # Now populate the result dictionary with the extracted data
            result['text'] = text
            result['method_used'] = current_method
            result['page_count'] = page_count
            result['character_count'] = len(text)
            result['word_count'] = len(text.split())
            
            # Assess the quality of the extracted text
            result['quality'] = assess_extraction_quality(text, page_count)
            
            # Check if this appears to be a scanned document
            result['is_scanned'] = detect_scanned_pdf(text, page_count)
            
            # Log successful extraction
            logger.info(
                f"Successfully extracted {result['word_count']} words "
                f"from {page_count} pages using {current_method}"
            )
            
            # Break out of the loop since we succeeded
            break
            
        except Exception as e:
            # This extraction method failed, log it and try the next one
            error_msg = f"Extraction failed with {current_method}: {str(e)}"
            logger.warning(error_msg)
            result['errors'].append(error_msg)
            continue
    
    # Check if all methods failed
    if result['method_used'] is None:
        error_msg = "All extraction methods failed"
        logger.error(f"{error_msg} for: {pdf_path}")
        result['errors'].append(error_msg)
    
    # Calculate how long the extraction took
    end_time = datetime.now()
    result['extraction_duration_seconds'] = (end_time - start_time).total_seconds()
    
    return result


# ============================================================================
# LIBRARY-SPECIFIC EXTRACTION FUNCTIONS
# ============================================================================
# These are internal "helper" functions that handle the specifics
# of each PDF library. They are called by extract_text_from_pdf().

def _extract_with_pdfplumber(pdf_path: str) -> Tuple[str, int]:
    """
    Extract text using pdfplumber library.
    
    pdfplumber is the best library for this project because it:
    - Preserves layout and structure
    - Handles tables well (important for court documents)
    - Correctly identifies headers and footers
    - Works well with multi-column layouts
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        tuple: (extracted_text, page_count)
    
    Raises:
        Exception: If extraction fails
    """
    # Open the PDF file using pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        # Get the number of pages
        page_count = len(pdf.pages)
        
        # Initialize an empty list to store text from each page
        text_parts = []
        
        # Iterate through each page and extract text
        for page in pdf.pages:
            # Extract text from this page
            # pdfplumber automatically handles layout and structure
            page_text = page.extract_text()
            
            # Only add non-empty pages
            if page_text:
                text_parts.append(page_text)
        
        # Combine all page texts with page breaks
        # Using double newline to clearly separate pages
        full_text = '\n\n'.join(text_parts)
        
        return full_text, page_count


def _extract_with_pymupdf(pdf_path: str) -> Tuple[str, int]:
    """
    Extract text using PyMuPDF (fitz) library.
    
    PyMuPDF is a good middle ground:
    - Faster than pdfplumber
    - Better quality than PyPDF2
    - Good for straightforward documents
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        tuple: (extracted_text, page_count)
    
    Raises:
        Exception: If extraction fails
    """
    # Open the PDF file using PyMuPDF (imported as 'fitz')
    doc = fitz.open(pdf_path)
    
    # Get the number of pages
    page_count = len(doc)
    
    # Initialize an empty list to store text from each page
    text_parts = []
    
    # Iterate through each page
    for page_num in range(page_count):
        # Get the page object
        page = doc[page_num]
        
        # Extract text from this page
        page_text = page.get_text()
        
        # Only add non-empty pages
        if page_text.strip():
            text_parts.append(page_text)
    
    # Close the document to free resources
    doc.close()
    
    # Combine all page texts with page breaks
    full_text = '\n\n'.join(text_parts)
    
    return full_text, page_count


def _extract_with_pypdf2(pdf_path: str) -> Tuple[str, int]:
    """
    Extract text using PyPDF2 library.
    
    PyPDF2 is the fastest but lowest quality option:
    - Very fast extraction
    - May miss complex layouts
    - May have issues with special characters
    - Use as last resort when other methods fail
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        tuple: (extracted_text, page_count)
    
    Raises:
        Exception: If extraction fails
    """
    # Open the PDF file in binary read mode
    with open(pdf_path, 'rb') as pdf_file:
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Get the number of pages
        page_count = len(pdf_reader.pages)
        
        # Initialize an empty list to store text from each page
        text_parts = []
        
        # Iterate through each page
        for page_num in range(page_count):
            # Get the page object
            page = pdf_reader.pages[page_num]
            
            # Extract text from this page
            page_text = page.extract_text()
            
            # Only add non-empty pages
            if page_text.strip():
                text_parts.append(page_text)
        
        # Combine all page texts with page breaks
        full_text = '\n\n'.join(text_parts)
        
        return full_text, page_count


# ============================================================================
# QUALITY ASSESSMENT FUNCTIONS
# ============================================================================

def detect_scanned_pdf(text: str, page_count: int) -> bool:
    """
    Detect if a PDF is likely scanned (image-based) rather than text-based.
    
    Scanned PDFs contain images of text rather than actual text. They require
    OCR (Optical Character Recognition) to extract text. This function uses
    heuristics to identify scanned documents so they can be flagged for
    special handling.
    
    The primary heuristic is word density: text-based PDFs typically have
    hundreds or thousands of words per page, while scanned PDFs extract
    very little or no text.
    
    Args:
        text (str): The extracted text to analyze
        page_count (int): Number of pages in the PDF
    
    Returns:
        bool: True if the PDF appears to be scanned, False otherwise
    
    Example:
        >>> text = extract_text_from_pdf('decision.pdf')['text']
        >>> is_scanned = detect_scanned_pdf(text, 10)
        >>> if is_scanned:
        ...     print("This document needs OCR processing")
    """
    # Handle edge cases
    if page_count == 0:
        return True  # No pages means something is wrong
    
    # Count the words in the text
    # A "word" is defined as any sequence of non-whitespace characters
    word_count = len(text.split())
    
    # Calculate words per page
    words_per_page = word_count / page_count
    
    # Heuristic thresholds:
    # - Legal documents typically have 300-600 words per page
    # - If we're getting less than 50 words per page, it's likely scanned
    # - This threshold is conservative to avoid false positives
    SCANNED_THRESHOLD = 50
    
    is_scanned = words_per_page < SCANNED_THRESHOLD
    
    # Log the detection result
    if is_scanned:
        logger.warning(
            f"PDF appears to be scanned: {words_per_page:.1f} words/page "
            f"({word_count} words across {page_count} pages)"
        )
    else:
        logger.debug(
            f"PDF appears to be text-based: {words_per_page:.1f} words/page"
        )
    
    return is_scanned


def assess_extraction_quality(text: str, page_count: int) -> str:
    """
    Assess the quality of extracted text using multiple heuristics.
    
    This function analyzes the extracted text to determine if the extraction
    was successful and of good quality. It checks for common issues that
    indicate poor extraction quality, such as:
    - Too little text (incomplete extraction)
    - Too many special characters (encoding issues)
    - Excessive whitespace (layout problems)
    - Very short "words" (fragmentation)
    
    Args:
        text (str): The extracted text to assess
        page_count (int): Number of pages in the PDF
    
    Returns:
        str: Quality assessment as one of:
            - "excellent": High-quality extraction, no issues detected
            - "good": Good extraction with minor issues
            - "fair": Acceptable extraction but with notable issues
            - "poor": Problematic extraction, may need manual review
            - "failed": Extraction failed or produced unusable text
    
    Example:
        >>> result = extract_text_from_pdf('decision.pdf')
        >>> print(f"Extraction quality: {result['quality']}")
    """
    # Handle empty or very short text
    if not text or len(text.strip()) < 100:
        return 'failed'
    
    # Initialize quality issues counter
    # We'll count how many quality issues we detect
    issues = []
    
    # ----------------------------------------
    # Check 1: Word density (words per page)
    # ----------------------------------------
    # Legal documents should have substantial text on each page
    word_count = len(text.split())
    words_per_page = word_count / page_count if page_count > 0 else 0
    
    # Thresholds for word density
    if words_per_page < 50:
        issues.append("very_low_word_density")
    elif words_per_page < 150:
        issues.append("low_word_density")
    # 150-600 words/page is normal for legal documents
    
    # ----------------------------------------
    # Check 2: Special characters ratio
    # ----------------------------------------
    # Too many special characters may indicate encoding problems
    # We count characters that are NOT letters, numbers, or common punctuation
    special_chars = re.findall(r'[^a-zA-Z0-9\s\.,;:!?\'"\-\(\)\[\]\/]', text)
    special_char_ratio = len(special_chars) / len(text) if len(text) > 0 else 0
    
    # Threshold: more than 10% special characters is suspicious
    if special_char_ratio > 0.10:
        issues.append("high_special_char_ratio")
    elif special_char_ratio > 0.05:
        issues.append("elevated_special_char_ratio")
    
    # ----------------------------------------
    # Check 3: Excessive line breaks
    # ----------------------------------------
    # Some PDFs extract with too many line breaks, fragmenting paragraphs
    consecutive_breaks = text.count('\n\n\n')
    if consecutive_breaks > page_count * 5:  # More than 5 triple-breaks per page
        issues.append("excessive_line_breaks")
    
    # ----------------------------------------
    # Check 4: Average word length
    # ----------------------------------------
    # Fragmentation issues often result in very short "words"
    words = text.split()
    if words:
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normal English words average 4-5 characters
        if avg_word_length < 3:
            issues.append("word_fragmentation")
        elif avg_word_length > 12:
            issues.append("abnormal_word_length")
    
    # ----------------------------------------
    # Check 5: Whitespace ratio
    # ----------------------------------------
    # Too much whitespace relative to content is a red flag
    whitespace_count = text.count(' ') + text.count('\n') + text.count('\t')
    whitespace_ratio = whitespace_count / len(text) if len(text) > 0 else 0
    
    # Threshold: more than 30% whitespace is excessive
    if whitespace_ratio > 0.30:
        issues.append("excessive_whitespace")
    
    # ----------------------------------------
    # Determine quality level based on issues
    # ----------------------------------------
    issue_count = len(issues)
    
    if issue_count == 0:
        quality = 'excellent'
    elif issue_count == 1:
        quality = 'good'
    elif issue_count == 2:
        quality = 'fair'
    else:
        quality = 'poor'
    
    # Log quality assessment
    if issues:
        logger.debug(f"Quality: {quality} (issues: {', '.join(issues)})")
    else:
        logger.debug(f"Quality: {quality}")
    
    return quality


# ============================================================================
# METADATA EXTRACTION FUNCTION
# ============================================================================

def extract_pdf_metadata(pdf_path: str) -> Dict[str, any]:
    """
    Extract metadata from a PDF file.
    
    This function retrieves file-level metadata that doesn't require reading
    the entire PDF content. It's useful for database records and quality tracking.
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        dict: Dictionary containing metadata with keys:
            - file_path (str): Full path to the file
            - filename (str): Just the filename without directory
            - file_size_bytes (int): Size of the file in bytes
            - file_size_mb (float): Size of the file in megabytes
            - exists (bool): Whether the file exists
            - is_readable (bool): Whether the file can be opened
            - creation_date (datetime): File creation timestamp (if available)
            - modification_date (datetime): File modification timestamp
            - page_count (int): Number of pages (if PDF can be opened)
            - pdf_version (str): PDF format version (if available)
            - errors (list): Any errors encountered
    
    Example:
        >>> metadata = extract_pdf_metadata('/path/to/decision.pdf')
        >>> print(f"File size: {metadata['file_size_mb']:.2f} MB")
        >>> print(f"Pages: {metadata['page_count']}")
    """
    # Initialize metadata dictionary
    metadata = {
        'file_path': pdf_path,
        'filename': os.path.basename(pdf_path),
        'file_size_bytes': 0,
        'file_size_mb': 0.0,
        'exists': False,
        'is_readable': False,
        'creation_date': None,
        'modification_date': None,
        'page_count': 0,
        'pdf_version': None,
        'errors': []
    }
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        metadata['errors'].append("File does not exist")
        return metadata
    
    metadata['exists'] = True
    
    # Get file size using os.path.getsize()
    try:
        file_size_bytes = os.path.getsize(pdf_path)
        metadata['file_size_bytes'] = file_size_bytes
        # Convert to megabytes (1 MB = 1,048,576 bytes)
        metadata['file_size_mb'] = file_size_bytes / (1024 * 1024)
    except Exception as e:
        metadata['errors'].append(f"Error getting file size: {str(e)}")
    
    # Get file timestamps
    try:
        # Get file statistics
        stat_info = os.stat(pdf_path)
        
        # Creation time (on Unix systems, this is actually ctime - last metadata change)
        # On Windows, this is the actual creation time
        metadata['creation_date'] = datetime.fromtimestamp(stat_info.st_ctime)
        
        # Modification time
        metadata['modification_date'] = datetime.fromtimestamp(stat_info.st_mtime)
    except Exception as e:
        metadata['errors'].append(f"Error getting file timestamps: {str(e)}")
    
    # Try to open the PDF and get additional metadata
    try:
        # Use pdfplumber to open the PDF and get page count
        with pdfplumber.open(pdf_path) as pdf:
            metadata['is_readable'] = True
            metadata['page_count'] = len(pdf.pages)
            
            # Try to get PDF metadata if available
            if pdf.metadata:
                # PDF version might be in metadata
                if 'Producer' in pdf.metadata:
                    metadata['pdf_version'] = str(pdf.metadata.get('Producer', 'Unknown'))
    except Exception as e:
        metadata['errors'].append(f"Error reading PDF: {str(e)}")
        metadata['is_readable'] = False
    
    return metadata


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def calculate_text_statistics(text: str) -> Dict[str, any]:
    """
    Calculate detailed statistics about extracted text.
    
    This function provides additional metrics beyond basic word/character counts
    that can be useful for quality assessment and research purposes.
    
    Args:
        text (str): The text to analyze
    
    Returns:
        dict: Dictionary containing:
            - word_count (int): Total number of words
            - character_count (int): Total number of characters
            - character_count_no_spaces (int): Characters excluding whitespace
            - line_count (int): Number of lines
            - paragraph_count (int): Approximate number of paragraphs
            - sentence_count (int): Approximate number of sentences
            - avg_word_length (float): Average length of words
            - avg_sentence_length (float): Average words per sentence
    """
    # Basic counts
    character_count = len(text)
    character_count_no_spaces = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))
    words = text.split()
    word_count = len(words)
    
    # Line count
    line_count = text.count('\n') + 1
    
    # Paragraph count (approximated by double line breaks)
    paragraph_count = text.count('\n\n') + 1
    
    # Sentence count (approximated by period, question mark, exclamation)
    # This is a rough estimate for legal documents
    sentence_count = text.count('.') + text.count('?') + text.count('!')
    
    # Average word length
    avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0
    
    # Average sentence length (words per sentence)
    avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
    
    return {
        'word_count': word_count,
        'character_count': character_count,
        'character_count_no_spaces': character_count_no_spaces,
        'line_count': line_count,
        'paragraph_count': paragraph_count,
        'sentence_count': sentence_count,
        'avg_word_length': round(avg_word_length, 2),
        'avg_sentence_length': round(avg_sentence_length, 2)
    }


# ============================================================================
# MODULE TEST FUNCTION
# ============================================================================

def test_extractor(pdf_path: str) -> None:
    """
    Test the text extractor with a sample PDF.
    
    This function demonstrates how to use the extraction functions and
    displays the results in a human-readable format.
    
    Args:
        pdf_path (str): Path to a PDF file to test with
    
    Example:
        >>> test_extractor('/path/to/sample_decision.pdf')
    """
    print("="*70)
    print("PDF TEXT EXTRACTION TEST")
    print("="*70)
    print(f"\nTesting file: {pdf_path}\n")
    
    # Extract metadata
    print("Extracting metadata...")
    metadata = extract_pdf_metadata(pdf_path)
    print(f"  File size: {metadata['file_size_mb']:.2f} MB")
    print(f"  Pages: {metadata['page_count']}")
    print(f"  Readable: {metadata['is_readable']}")
    if metadata['errors']:
        print(f"  Metadata errors: {', '.join(metadata['errors'])}")
    
    # Extract text
    print("\nExtracting text (auto mode)...")
    result = extract_text_from_pdf(pdf_path, method='auto')
    
    print(f"\n  Method used: {result['method_used']}")
    print(f"  Pages: {result['page_count']}")
    print(f"  Words: {result['word_count']}")
    print(f"  Characters: {result['character_count']}")
    print(f"  Quality: {result['quality']}")
    print(f"  Is scanned: {result['is_scanned']}")
    print(f"  Duration: {result['extraction_duration_seconds']:.2f} seconds")
    
    if result['errors']:
        print(f"\n  Errors: {', '.join(result['errors'])}")
    
    # Show text sample
    if result['text']:
        print("\nText sample (first 500 characters):")
        print("-" * 70)
        print(result['text'][:500])
        print("-" * 70)
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


# ============================================================================
# MAIN EXECUTION (for testing)
# ============================================================================

if __name__ == "__main__":
    # This section only runs if you execute this file directly
    # It's useful for testing the module
    
    import sys
    
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check if a PDF path was provided as command line argument
    if len(sys.argv) > 1:
        test_pdf_path = sys.argv[1]
        test_extractor(test_pdf_path)
    else:
        print("Usage: python text_extractor.py <path_to_pdf>")
        print("\nThis module provides functions for extracting text from PDFs.")
        print("Import it in your scripts to use the extraction functions.")
