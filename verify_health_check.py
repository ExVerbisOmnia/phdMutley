
import sys
import os
import time
import threading
import requests
from flask import Flask

# Add railway directory to path
sys.path.append(os.path.abspath('railway'))

# Import app from api_server
from api_server import app

def run_server():
    app.run(port=5001)

def test_health_check():
    # Start server in a thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Give it a moment to start
    time.sleep(2)
    
    try:
        # Test new health check
        print("Testing /health endpoint...")
        response = requests.get('http://127.0.0.1:5001/health')
        if response.status_code == 200 and response.text == "OK":
            print("SUCCESS: /health returned 200 OK")
        else:
            print(f"FAILURE: /health returned {response.status_code} {response.text}")
            sys.exit(1)
            
        # Test old health check (might fail if DB not connected, but should exist)
        print("Testing /api/health endpoint...")
        response = requests.get('http://127.0.0.1:5001/api/health')
        print(f"/api/health returned {response.status_code}")
        # We don't exit on failure here because DB might not be available in this test env
        
    except Exception as e:
        print(f"Error during testing: {e}")
        sys.exit(1)

if __name__ == '__main__':
    test_health_check()
