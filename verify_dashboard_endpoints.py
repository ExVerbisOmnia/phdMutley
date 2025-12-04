
import sys
import os
import time
import threading
import requests
import json
from flask import Flask

# Add railway directory to path
sys.path.append(os.path.abspath('railway'))

# Import app from api_server
from api_server import app

def run_server():
    app.run(port=5002)

def test_endpoints():
    # Start server in a thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Give it a moment to start
    time.sleep(2)
    
    base_url = 'http://127.0.0.1:5002'
    
    endpoints = [
        '/api/custom/citations-received',
        '/api/custom/flow',
        '/api/custom/citations-by-jurisdiction?source_jurisdiction=Test'
    ]
    
    try:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            print(f"Testing {url}...")
            response = requests.get(url)
            
            if response.status_code == 200:
                print(f"SUCCESS: {endpoint} returned 200 OK")
                try:
                    data = response.json()
                    print(f"Data type: {type(data)}")
                except:
                    print("Failed to parse JSON")
            else:
                print(f"FAILURE: {endpoint} returned {response.status_code}")
                # We expect 200 even if empty list, as long as DB query works or returns empty
                # Note: In this test env, DB might not be populated, so empty list is expected.
                # If DB connection fails, it might return 500.
                
    except Exception as e:
        print(f"Error during testing: {e}")

if __name__ == '__main__':
    test_endpoints()
