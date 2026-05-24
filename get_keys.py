import requests, re
url = 'https://unitedpharmacy.sa/ar/'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
app_id = re.search(r'applicationId[\"\'\s:]+([A-Z0-9]+)', r.text)
api_key = re.search(r'apiKey[\"\'\s:]+([A-Za-z0-9]+)', r.text)
print('United App ID:', app_id.group(1) if app_id else 'None')
print('United API Key:', api_key.group(1) if api_key else 'None')

url_nahdi = 'https://www.nahdionline.com/ar-sa/'
r2 = requests.get(url_nahdi, headers={'User-Agent': 'Mozilla/5.0'})
app_id2 = re.search(r'\"appId\"\:\"([A-Z0-9]+)\"', r2.text)
api_key2 = re.search(r'\"apiKey\"\:\"([A-Za-z0-9]+)\"', r2.text)
print('Nahdi App ID:', app_id2.group(1) if app_id2 else 'None')
print('Nahdi API Key:', api_key2.group(1) if api_key2 else 'None')
