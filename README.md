# eProcurement AI Pipeline

An intelligent web scraping and product classification system that extracts product information from e-commerce websites and automatically classifies them using AI-powered semantic search and machine learning.

## 🎯 Overview

This pipeline combines web scraping capabilities with advanced AI classification to:
- **Scrape** product data from manufacturer websites (currently supports Sika and Flex Tools)
- **Extract** comprehensive product information including names, descriptions, technical specifications, and datasheets
- **Classify** products into a hierarchical taxonomy using semantic embeddings and optional LLM reranking
- **Export** structured, classified product data in JSONL format

## 🏗️ Architecture

The system consists of three main components:

### 1. **Web Scraping (Scrapy)**
   - Custom spiders for each manufacturer website
   - Intelligent link discovery and product page detection
   - Robust data extraction with fallback mechanisms
   - Support for both static and dynamic content

### 2. **AI Classification**
   - Semantic search using sentence transformers (`all-MiniLM-L6-v2`)
   - FAISS-based vector similarity search for fast taxonomy matching
   - Optional LLM reranking for improved accuracy (`TinyLlama`)
   - Hierarchical classification tree support

### 3. **Data Pipeline**
   - Automatic classification during scraping
   - Structured JSONL export format
   - Caching for improved performance

## 📁 Project Structure

```
eProcurement_AI_Pipeline/
├── product_scraper/          # Scrapy project
│   ├── spiders/
│   │   ├── sika_spider.py    # Sika website crawler
│   │   └── flex_spider.py    # Flex Tools website crawler
│   ├── items.py              # Product data structure
│   ├── pipelines.py          # Classification pipeline
│   └── settings.py           # Scrapy configuration
├── classification/           # AI classification module
│   ├── classify_products.py  # Main classifier with FAISS + LLM
│   ├── data/
│   │   └── classification_tree.csv  # Taxonomy definition
│   └── test_one_product.py   # Testing utilities
├── exports/                  # Full product exports (JSONL)
├── output/                   # Classified product outputs
├── discovered_product_links/ # Discovered product URLs
├── requirements.txt          # Python dependencies
├── scrapy.cfg               # Scrapy configuration
└── README.md                # This file
```

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd eProcurement_AI_Pipeline
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```


## 📖 Usage

### Running a Spider

To scrape products from a specific manufacturer:

```bash
# Scrape Sika products
scrapy crawl sika_crawler -o output/sika_products.jsonl

# Scrape Flex Tools products
scrapy crawl flex_crawler -o output/flex_products.jsonl
```

### Classification Options

The pipeline automatically classifies products during scraping. The classification uses:
- **Embedding-only mode** (default): Fast, uses semantic similarity
- **LLM reranking mode**: More accurate but slower, requires LLM model download

To enable LLM reranking, modify `classify_products.py`:
```python
classification_result = self.classifier.classify_product(product_data, use_llm=True)
```

### Testing Classification

Test classification on a single product:

```python
from classification.classify_products import ProductClassifier
import json

classifier = ProductClassifier()
with open('exports/sika_products_full.jsonl', 'r') as f:
    product = json.loads(next(f))

result = classifier.classify_product(product, use_llm=False)
print(result)
```

## 📊 Data Format

### Input (Scraped Product)
```json
{
  "brand": "Sika",
  "product_name": "Sikagrout Cable PT",
  "model_article_number": "12345",
  "short_description": "High-performance grouting material...",
  "long_description": "Detailed product description...",
  "product_image_url": "https://...",
  "datasheet_url": "https://...",
  "technical_specifications": {
    "Compressive Strength": "50 MPa",
    "Temperature Range": "-20°C to +80°C"
  },
  "product_url": "https://gcc.sika.com/...",
  "type_id": null,
  "classification_path": null
}
```

### Output (Classified Product)
```json
{
  "product_name": "Sikagrout Cable PT",
  "product_url": "https://gcc.sika.com/...",
  "type_id": 1234,
  "classification_path": "Construction > Grouting > Cementitious Grouts"
}
```

## ⚙️ Configuration

### Scrapy Settings (`product_scraper/settings.py`)
- `CONCURRENT_REQUESTS`: Number of parallel requests (default: 32)
- `DOWNLOAD_DELAY`: Delay between requests in seconds (default: 0.5)
- `LOG_LEVEL`: Logging verbosity (default: 'INFO')
- `ROBOTSTXT_OBEY`: Respect robots.txt (default: True)

### Classification Settings (`classification/classify_products.py`)
- `TOP_K`: Number of candidate categories to retrieve (default: 5)
- `EMBEDDING_MODEL`: Sentence transformer model (default: "all-MiniLM-L6-v2")
- `LLM_MODEL`: LLM for reranking (default: "TinyLlama/TinyLlama-1.1B-Chat-v1.0")

## 🔧 Customization

### Adding a New Spider

1. Create a new spider file in `product_scraper/spiders/`
2. Inherit from `scrapy.Spider`
3. Implement:
   - `start_urls`: Initial URLs to crawl
   - `parse_category_page()`: Link discovery logic
   - `parse_product_page()`: Product data extraction
   - `is_product_page()`: Product page detection

Example:
```python
import scrapy
from ..items import ProductItem

class MySpider(scrapy.Spider):
    name = 'my_spider'
    allowed_domains = ['example.com']
    start_urls = ['https://example.com/products']
    
    def parse_product_page(self, response):
        item = ProductItem()
        item['brand'] = 'MyBrand'
        item['product_name'] = response.css('h1::text').get()
        # ... extract other fields
        yield item
```

### Updating Taxonomy

Edit `classification/data/classification_tree.csv` with your taxonomy structure:
- `id`: Unique category ID
- `name`: Category name
- `parent_id`: Parent category ID (null for root)
- `path`: Dot-separated path (e.g., "1.2.3")

## 🧪 Testing

Run classification tests:
```bash
cd classification
python test_one_product.py
```

## 📝 Notes

- **Caching**: FAISS index and taxonomy are cached in `classification/.cache/` for faster subsequent runs
- **Rate Limiting**: Adjust `DOWNLOAD_DELAY` to respect website rate limits
- **Robots.txt**: The pipeline respects robots.txt by default
- **Memory**: LLM mode requires significant RAM; embedding-only mode is more memory-efficient

## 🤝 Contributing

1. Follow PEP 8 style guidelines
2. Add docstrings to new functions
3. Test your changes before submitting
4. Update this README if adding new features

## 📄 License

[Specify your license here]

## 🙏 Acknowledgments

- Built with [Scrapy](https://scrapy.org/)
- Classification powered by [sentence-transformers](https://www.sbert.net/)
- Vector search using [FAISS](https://github.com/facebookresearch/faiss)
- Optional LLM support via [Hugging Face Transformers](https://huggingface.co/)