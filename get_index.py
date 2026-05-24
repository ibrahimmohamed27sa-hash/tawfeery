import requests, re
url = 'https://unitedpharmacy.sa/ar/'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
index = re.search(r'indexName[\"\'\s:]+([A-Za-z0-9_]+)', r.text)
print('United Index Name:', index.group(1) if index else 'None')
