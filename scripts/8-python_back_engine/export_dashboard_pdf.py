import os
import time
import argparse
from playwright.sync_api import sync_playwright

def export_dashboard_to_pdf(output_path='dashboard_export.pdf', dashboard_path='dashboard.html'):
    """
    Export the dashboard to a PDF file using Playwright.
    """
    # Get absolute path to dashboard file
    if not os.path.isabs(dashboard_path):
        dashboard_path = os.path.abspath(dashboard_path)
    
    file_url = f"file://{dashboard_path}"
    print(f"Opening dashboard at: {file_url}")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set viewport size for better layout
        page.set_viewport_size({"width": 1280, "height": 1024})
        
        # Navigate to dashboard
        page.goto(file_url)
        
        print("Waiting for data to load...")
        
        # Wait for API data to populate
        # We check if the total citations element has a number (not '-')
        try:
            page.wait_for_function(
                "document.getElementById('total-citations').textContent !== '-'",
                timeout=10000
            )
            # Give a little extra time for charts to animate/render
            time.sleep(2)
        except Exception as e:
            print(f"Warning: Timeout waiting for data load. PDF might be incomplete. Error: {e}")

        # Generate PDF
        print(f"Generating PDF to: {output_path}")
        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"}
        )
        
        browser.close()
        print("✓ Export complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export Dashboard to PDF')
    parser.add_argument('--output', '-o', default='dashboard_export.pdf', help='Output PDF file path')
    parser.add_argument('--input', '-i', default='dashboard.html', help='Input HTML file path')
    
    args = parser.parse_args()
    
    export_dashboard_to_pdf(args.output, args.input)
