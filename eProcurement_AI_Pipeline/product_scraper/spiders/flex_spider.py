import scrapy
import re
import json
from urllib.parse import urljoin, urlparse
from ..items import ProductItem 

class FlexSpider(scrapy.Spider):
    name = "flex_crawler"
    allowed_domains = ['www.flex-tools.com']

    start_urls = [
        'https://www.flex-tools.com/en/products',
        'https://www.flex-tools.com/en/accessories',
    ]

    visited_urls = set()
    processed_products = set()

    # --- 1. INITIAL REQUEST ---
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_category_page
            )

    # --- 2. CATEGORY & PRODUCT DISCOVERY ---
    def parse_category_page(self, response):
        url = response.url
        if url in self.visited_urls:
            return
        self.visited_urls.add(url)
        self.logger.info(f"🔍 Scanning: {url}")

        # 1️⃣ Check if this page is a product page
        if self.is_product_page(response):
            self.logger.info(f"📦 Product detected: {url}")
            yield from self.parse_product_page(response)
            return

        # 2️⃣ Otherwise, follow links to discover more pages
        for link in response.css('a::attr(href)').getall():
            if not link:
                continue
            full_url = urljoin(response.url, link.strip())
            if not self.is_valid_domain(full_url):
                continue
            if full_url in self.visited_urls:
                continue
            yield scrapy.Request(
                full_url,
                callback=self.parse_category_page
            )

    # --- 3. PRODUCT DETECTION HELPER ---
    def is_product_page(self, response):
        url = response.url
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 4 or path_parts[0] != "en":
            return False
        if path_parts[1] not in ("products", "accessories"):
            return False

        last_segment = path_parts[-1].lower()
        has_digits = bool(re.search(r"\d", last_segment))
        has_hyphenated_slug = "-" in last_segment
        slug_is_not_generic = last_segment not in {
            "products", "accessories", "special-tools", "promotions"
        }

        url_signal = has_digits or (has_hyphenated_slug and slug_is_not_generic)

        has_h1 = response.css("h1::text").get() is not None
        has_product_grid = response.css(
            ".product-list, .product-grid, .product-card, .product-tile"
        ).get() is not None

        page_text = " ".join(response.css("body ::text").getall()).lower()
        has_tech_keywords = any(
            kw in page_text
            for kw in (
                "technical data",
                "technical information",
                "specifications",
                "article number",
                "item no",
                "scope of delivery",
            )
        )

        return (has_h1 and not has_product_grid and (url_signal or has_tech_keywords)) or (has_tech_keywords and url_signal)

    def is_valid_domain(self, url):
        parsed = urlparse(url)
        if parsed.netloc != "www.flex-tools.com":
            return False
        return parsed.path.startswith("/en/products") or parsed.path.startswith("/en/accessories")

    # --- 4. PRODUCT EXTRACTION ---
    def parse_product_page(self, response):
        url = response.url
        if url in self.processed_products:
            self.logger.info(f"Already processed: {url}")
            return
        self.processed_products.add(url)

        self.logger.info(f"Parsing product page: {url}")

        item = ProductItem()

        # --- JSON-LD extraction ---
        json_ld_scripts = response.css('script[type="application/ld+json"]::text').getall()
        self.logger.debug(f"Found {len(json_ld_scripts)} JSON-LD scripts")
        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    for d in data:
                        if d.get('@type') == 'Product':
                            data = d
                            break
                if data.get('@type') == 'Product':
                    item['product_name'] = self.clean_text(data.get('name'))
                    item['model_article_number'] = self.clean_text(data.get('mpn'))
                    item['short_description'] = self.clean_text(data.get('description'))
                    item['long_description'] = self.clean_text(data.get('description'))
                    tech = data.get('additionalProperty', [])
                    item['technical_specifications'] = {p.get('propertyID'): p.get('value') for p in tech if p.get('propertyID') and p.get('value')}
                    if data.get('image'):
                        item['product_image_url'] = response.urljoin(data.get('image'))
                    self.logger.info("Extracted product info from JSON-LD")
                    break
            except Exception as e:
                self.logger.warning(f"Failed to parse JSON-LD: {e}", exc_info=True)

        # --- CSS fallback for product name ---
        if not item['product_name']:
            for sel in ['h1.product-title::text', 'h1.title::text', 'h1::text', 'title::text']:
                name = response.css(sel).get()
                if name:
                    item['product_name'] = self.clean_text(name.replace('- FLEX', ''))
                    self.logger.debug(f"Found product name via selector {sel}: {item['product_name']}")
                    break

        # --- Short description fallback ---
        if not item['short_description']:
            desc_selectors = ['.product-info-description', '.product-description', '.short-description', '.description']
            for sel in desc_selectors:
                desc = response.css(sel).get()
                if desc:
                    item['short_description'] = self.clean_text(desc)
                    break
            if not item['short_description']:
                paragraphs = response.css('p::text').getall()
                meaningful = [self.clean_text(p) for p in paragraphs if len(self.clean_text(p)) > 50]
                if meaningful:
                    item['short_description'] = meaningful[0][:200] + '...' if len(meaningful[0]) > 200 else meaningful[0]

        # --- Technical specs from tables ---
        tables = response.css('table.spec-table, table.technical-data, table.product-attributes')
        specs = {}
        for table in tables:
            for row in table.css('tr'):
                cells = row.css('td, th')
                if len(cells) >= 2:
                    key = self.clean_text(cells[0].get())
                    value = self.clean_text(cells[1].get())
                    if key and value:
                        specs[key.lower()] = value
        if specs:
            item['technical_specifications'] = specs

        # --- Datasheet PDF ---
        pdf_links = response.css('a[href$=".pdf"]::attr(href)').getall()
        for link in pdf_links:
            if any(k in link.lower() for k in ['datasheet', 'manual', 'spec']):
                item['datasheet_url'] = response.urljoin(link)
                break

        # --- Model number fallback ---
        if not item['model_article_number'] and item['product_name']:
            match = re.match(r'^([A-Z0-9\s/-]+?)(?:\s+-\s+FLEX)?$', item['product_name'])
            if match:
                candidate = match.group(1).strip()
                if any(c.isdigit() for c in candidate):
                    item['model_article_number'] = candidate

        # --- Product image fallback ---
        if not item['product_image_url']:
            img = response.css('meta[property="og:image"]::attr(content), meta[name="og:image"]::attr(content)').get()
            if img:
                item['product_image_url'] = response.urljoin(img)

        item['type_id'] = ''
        item['classification_path'] = ''

        self.logger.info(f"✅ Yielding product: {item['product_name']} | URL: {url}")
        yield item

    def clean_text(self, text):
        if not text:
            return ''
        cleaned_text = re.sub(r'<[^>]+>', '', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        return cleaned_text.strip()