import requests
import json
import subprocess
from datetime import datetime
import time
import os
import sys

def fetch_agent_status():
    url = '__CFG_0153__'
    username = '__CFG_0154__'
    password = '__CFG_0002__'
    time_now = datetime.now()
    formated_time = time_now.strftime('%Y-%m-%d %H:%M:%S')
    params = {'page': '1', 'perPage': '2000', 'kuery': 'status:error or status:degraded or status:offline', 'sortField': 'enrolled_at', 'sortOrder': 'desc', 'showInactive': 'false', 'showUpgradeable': 'false', 'getStatusSummary': 'true', 'withMetrics': 'true'}
    try:
        response = requests.get(url, auth=(username, password), params=params)
        response.raise_for_status()
        python_path = 'python'
        poster_path = '/usr/src/app/ticket_creater.py'
        caller = '__CFG_0030__'
        alert_type = 'Elastic_Agent_Status'
        data = response.json()
        for item in data.get('items', []):
            status = item.get('status')
            host_name = item.get('local_metadata', {}).get('host', {}).get('name')
            try:
                subprocess.run(['%s' % python_path, '%s' % poster_path, '%s' % caller, '%s' % alert_type, '%s' % host_name, '%s' % formated_time, '%s' % status])
            except subprocess.CalledProcessError as e:
                print('Error calling ticket poster script:', e)
    except requests.RequestException as e:
        print('Error fetching data:', e)

def run_daemon():
    while True:
        print(f'Starting agent status check at {datetime.now()}')
        fetch_agent_status()
        print(f'Sleeping for 30 minutes...')
        time.sleep(1)
run_daemon()
