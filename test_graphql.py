import requests

url = 'https://www.nahdionline.com/graphql'
query = """
{
  products(search: "panadol", pageSize: 10) {
    items {
      name
      sku
      price_range {
        minimum_price {
          regular_price {
            value
          }
        }
      }
      image {
        url
      }
      url_key
    }
  }
}
"""

headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Store': 'ar'
}

try:
    res = requests.post(url, json={'query': query}, headers=headers)
    print(res.status_code)
    print(res.text[:500])
except Exception as e:
    print(e)
