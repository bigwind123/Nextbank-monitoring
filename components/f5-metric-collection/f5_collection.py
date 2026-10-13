import requests
import urllib3
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
f5_base_url = '__CFG_1566__'
f5_username = '__CFG_1567__'
f5_password = '__CFG_0023__'
es_url = '__CFG_1568__'
es_token = '__CFG_0024__'
f5_session = requests.Session()
f5_session.auth = (f5_username, f5_password)
f5_session.verify = False
es_session = requests.Session()
es_session.verify = False
es_session.headers.update({'Authorization': f'ApiKey {es_token}', 'Content-Type': 'application/json'})

def get_all_pools():
    """Get all pool names"""
    pools_url = f'{f5_base_url}/'
    print(f'Requesting: {pools_url}')
    response = f5_session.get(pools_url)
    response.raise_for_status()
    pools_data = response.json()
    pools = [pool['fullPath'].split('/')[-1] for pool in pools_data.get('items', [])]
    return pools

def get_pool_members_status(pool_name):
    """Get pool members and their status"""
    members_url = f'{f5_base_url}/~Common~{pool_name}/members'
    print(f'Requesting: {members_url}')
    response = f5_session.get(members_url)
    response.raise_for_status()
    members_data = response.json()
    members_info = []
    items = members_data.get('items', [])
    for member in items:
        member_name = member.get('name', 'unknown')
        original_state = member.get('state', 'unknown')
        stats_url = f'{f5_base_url}/~Common~{pool_name}/members/~Common~{member_name}/stats'
        print(f'Requesting: {stats_url}')
        try:
            stats_response = f5_session.get(stats_url)
            stats_response.raise_for_status()
            stats_data = stats_response.json()
            entries = list(stats_data.get('entries', {}).values())
            if entries:
                availability = entries[0].get('nestedStats', {}).get('entries', {}).get('status.availabilityState', {}).get('description', 'offline')
                if availability == 'available':
                    final_state = 'up'
                else:
                    final_state = 'down'
            else:
                final_state = original_state
        except Exception as e:
            print(f'Fail to get member {member_name} stats, using original status. Error: {e}')
            final_state = original_state
        members_info.append({'member_name': member_name, 'member_status': final_state})
    return members_info

def get_pool_current_connections_and_availability(pool_name):
    """Get pool current connection count and availability state"""
    stats_url = f'{f5_base_url}/~Common~{pool_name}/stats'
    print(f'Requesting: {stats_url}')
    try:
        response = f5_session.get(stats_url)
        response.raise_for_status()
        data = response.json()
        entries = list(data.get('entries', {}).values())
        if entries:
            stats = entries[0].get('nestedStats', {}).get('entries', {})
            connections = stats.get('serverside.curConns', {}).get('value', 0)
            availability = stats.get('status.availabilityState', {}).get('description', 'offline')
            availability_state = 'up' if availability == 'available' else 'down'
            return (connections, availability_state)
    except Exception as e:
        print(f'Failed to get pool stats: {pool_name}, error: {e}')
    return (0, 'down')

def send_to_elasticsearch(pool_name, members_info, connections, availability_state):
    """Send data to Elasticsearch"""
    payload = {'@timestamp': datetime.utcnow().isoformat() + 'Z', 'pool_name': pool_name, 'current_connections': connections, 'availability_state': availability_state}
    for idx, member in enumerate(members_info, start=1):
        member_field = f'member{idx}'
        payload[member_field] = {'member_name': member['member_name'], 'member_status': member['member_status']}
    print(f'Sending data to Elasticsearch: {es_url}')
    response = es_session.post(es_url, json=payload)
    response.raise_for_status()
    print(f'Sent to Elasticsearch: {pool_name} with {len(members_info)} members, connections: {connections}, status: {availability_state}')

def main():
    pools = get_all_pools()
    for pool in pools:
        members_info = get_pool_members_status(pool)
        connections, availability_state = get_pool_current_connections_and_availability(pool)
        print(f'Pool: {pool}, members: {len(members_info)}, connections: {connections}, status: {availability_state}')
        send_to_elasticsearch(pool, members_info, connections, availability_state)
if __name__ == '__main__':
    main()
