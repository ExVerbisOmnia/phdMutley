#!/usr/bin/env python3
"""
Climate Litigation Database Filter Script
Filters the complete database to keep only court decisions (Document Type == 'Decision')
"""

import pandas as pd
import sys
from pathlib import Path


def filter_decisions(input_file, output_file):
    """
    Filter the climate litigation database to keep only decisions.
    
    Args:
        input_file (str): Path to the input Excel file (baseCompleta.xlsx)
        output_file (str): Path to save the filtered Excel file
    """
    
    # Load the Excel file into a pandas DataFrame
    # This reads all rows and columns from the spreadsheet
    print(f"Loading data from {input_file}...")
    df = pd.read_excel(input_file)
    
    # Display initial statistics
    # Shows total number of entries before filtering
    print(f"Total entries in original database: {len(df)}")
    print(f"\nDocument Type distribution:")
    print(df['Document Type'].value_counts())
    
    # Filter the DataFrame to keep only rows where Document Type is 'Decision'
    # The == operator creates a boolean mask, and df[mask] returns only True rows
    print("\nFiltering for decisions only...")
    filtered_df = df[df['Document Type'] == 'Decision']
    
    # Display statistics after filtering
    # Shows how many decisions were found
    print(f"\nTotal decisions found: {len(filtered_df)}")
    print(f"Percentage of total entries: {len(filtered_df)/len(df)*100:.2f}%")
    
    # Save the filtered DataFrame to a new Excel file
    # index=False prevents pandas from writing row numbers as a column
    print(f"\nSaving filtered data to {output_file}...")
    filtered_df.to_excel(output_file, index=False)
    
    print("Done! Filtered database saved successfully.")
    
    return filtered_df


if __name__ == "__main__":
    # Default file paths
    # These can be modified or passed as command-line arguments
    input_file = "../../data/raw/baseCompleta.xlsx"
    output_file = "../../data/processed/baseDecisions.xlsx"
    
    # Check if custom file paths were provided as command-line arguments
    # Usage: python baseFilter.py [input_file] [output_file]
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # Verify that the input file exists before attempting to read it
    # Prevents cryptic errors if file is missing
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    try:
        # Execute the filtering function
        # This is the main workflow: load -> filter -> save
        filter_decisions(input_file, output_file)
        
    except Exception as e:
        # Catch and display any errors that occur during processing
        # Helps with debugging if something goes wrong
        print(f"\nError occurred: {str(e)}")
        sys.exit(1)