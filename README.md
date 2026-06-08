# Tawfeery - Smart Pharmacy Price Comparison

Compare prices across Saudi Arabia's top pharmacies: **Nahdi Online**, **United Pharmacy**, and **Al-Dawaa**. Find the best deals, discover alternatives, and save money on healthcare products.

## Features

- **Real-time Price Comparison** - Search any product and compare prices across 3 major pharmacies
- **Smart Product Matching** - AI-powered matching identifies identical products across stores
- **Alternative Suggestions** - When a product isn't available, find similar alternatives from the same brand
- **Cold Start Recovery** - Automatic retry with countdown for Render free tier cold starts
- **Mobile-First Design** - Responsive interface optimized for smartphones
- **Arabic/English Support** - Full RTL support with transliteration for cross-language search

## Live Demo

Visit: [https://tawfeery.onrender.com](https://tawfeery.onrender.com)

## How It Works

1. **Search** - Enter a product name in Arabic or English
2. **Compare** - View prices from all three pharmacies side-by-side
3. **Save** - Add items to your basket and see total cost at each store
4. **Discover** - Get alternative product suggestions when your preferred item isn't available

## Tech Stack

- **Backend**: Flask + Gunicorn (gevent workers)
- **Scraping**: Cloudscraper + Magento REST API (Nahdi), Algolia API (United), OCC API (Al-Dawaa)
- **Database**: SQLite with WAL mode for concurrent access
- **Frontend**: Vanilla JavaScript with Server-Sent Events
- **Deployment**: Render.com (free tier)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Homepage with deals |
| `GET /api/search?q=product` | Search products (SSE stream) |
| `GET /api/deals` | Get current deals |
| `GET /api/stats` | Site statistics |
| `GET /admin` | Admin dashboard |
| `GET /_ping` | Health check |

## Product Matching Engine

The `match_products.py` script uses AI-powered matching:

1. **Smart Parser** - Extracts brand, product, size, and form from product names
2. **Exact Matching** - Identifies identical products across stores
3. **Alternative Detection** - Finds similar products when exact match unavailable
4. **Price Optimization** - Calculates best price across all stores

### Match Statistics

| Metric | Count |
|--------|-------|
| Total Products | 87,720 |
| Unique Products | 84,300 |
| 3-Store Matches | 79 |
| 2-Store Matches | 1,600 |
| With Alternatives | 14,429 |

## Deployment

### Render.com

1. Fork this repository
2. Connect to Render
3. Create a Web Service
4. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app -k gevent -w 2 --worker-connections 1000 --timeout 60`
   - **Environment**: Python 3.13

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ADMIN_PASSWORD` | Admin dashboard password | Yes |
| `PORT` | Server port | No (auto) |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details

## Acknowledgments

- Nahdi Online, United Pharmacy, and Al-Dawaa for their public APIs
- The open-source community for amazing tools and libraries

---

**Built with ❤️ for Saudi healthcare consumers**
