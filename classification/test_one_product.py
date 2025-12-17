import json
from classify_products import ProductClassifier

classifier = ProductClassifier()

# Load one product 
with open(r"C:\Users\shaym\Downloads\eProcurement_ai\eProcurement_AI_Pipeline\exports\sika_products_full.jsonl", "r", encoding="utf-8") as f:
    product = json.loads(next(f))

result = classifier.classify_product(product, use_llm=False)  # start without LLM

print("PRODUCT:", product["product_name"])
print("CLASSIFICATION RESULT:")
print(result)