import requests, json

headers = {
    'X-Algolia-API-Key': 'NGFkYzM5MDgzYjA0YmI2YzdlYjk4YjIwNDFjZjQzZTg2ZDQ4M2Q0ZGM5ZTVjYTgxYTNjZWRlMjllZDg0YTg3Y3RhZ0ZpbHRlcnM9',
    'X-Algolia-Application-Id': 'Y1GOQ9DTV8'
}
url = 'https://Y1GOQ9DTV8-dsn.algolia.net/1/indexes/*/queries'
payload = {
  "requests": [
    {
      "indexName": "unitedpharmacy_livear_products",
      "params": "query=panadol&hitsPerPage=5"
    }
  ]
}

r = requests.post(url, headers=headers, json=payload)
print(r.status_code)
if r.status_code == 200:
    data = r.json()
    hits = data.get('results', [{}])[0].get('hits', [])
    for h in hits:
        print(h.get('name'), h.get('price'))
else:
    print(r.text)
