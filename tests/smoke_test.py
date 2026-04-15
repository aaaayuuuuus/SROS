import requests, json

base = 'http://127.0.0.1:5000'

# Health check
h = requests.get(f'{base}/health').json()
print('HEALTH:', h)

# Register
r = requests.post(f'{base}/auth/register', json={
    'name': 'Test User', 'email': 'verify@test.in', 'password': 'Verify123!'
})
print('REGISTER status:', r.status_code)
token = r.json()['data']['access_token']

# ME
me = requests.get(f'{base}/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
print('ME:', me['data']['name'])

# Optimize
res = requests.post(
    f'{base}/api/optimize',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'origin': 'Delhi', 'destination': 'Agra', 'vehicle': 'car_electric', 'priority': 'balanced'}
).json()
print('ROUTES:', [r['type'] for r in res['data']['routes']])
print('CO2 saved:', [r['emissions']['co2_saved_kg'] for r in res['data']['routes']])
print('NEW ACH:', ascii(res['data'].get('new_achievements', [])))

# Stats
s = requests.get(f'{base}/api/stats', headers={'Authorization': f'Bearer {token}'}).json()
print('STATS trips:', s['data']['total_trips'])
print('STATS co2_saved:', s['data']['total_co2_saved_kg'])

# Leaderboard
lb = requests.get(f'{base}/api/leaderboard').json()
print('LEADERBOARD entries:', len(lb['data']))

# Achievements
ach = requests.get(f'{base}/api/achievements', headers={'Authorization': f'Bearer {token}'}).json()
earned = sum(1 for b in ach['data'] if b['earned'])
print(f'ACHIEVEMENTS total: {len(ach["data"])} | earned: {earned}')
