# --- REACTOR & HANDLERS ---
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

#DOWNLOAD_HANDLERS = {
#    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#}

# --- PERFORMANCE & STABILITY ---
CONCURRENT_REQUESTS = 32
DOWNLOAD_DELAY = 0.5
LOG_LEVEL = 'INFO'

#PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  

# --- REQUEST BLOCKING (Speed boost) ---
#PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in ["image", "font", "media"] or \
#                                        "google-analytics" in req.url or \
#                                        "googletagmanager" in req.url

# --- BROWSER SETTINGS ---
#PLAYWRIGHT_LAUNCH_OPTIONS = {
#    "headless": True,
#    "timeout": 20000,  
#}

# --- PROJECT STRUCTURE ---
BOT_NAME = 'product_scraper'
SPIDER_MODULES = ['product_scraper.spiders']
NEWSPIDER_MODULE = 'product_scraper.spiders'

# --- ROBOTSTXT ---
ROBOTSTXT_OBEY = True

ITEM_PIPELINES = {
   'product_scraper.pipelines.ClassificationPipeline': 300,
}

FEED_EXPORT_ENCODING = 'utf-8'