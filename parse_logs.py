
import json

with open('logs/deployment_logs.json', 'r') as f:
    logs = json.load(f)

for log in logs:
    print(f"{log['timestamp']} - {log['message']}")
