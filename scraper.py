import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from itertools import product
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(
    filename="shl_scraper.log",
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BASE_URL = "https://www.shl.com"
CATALOG_URL = BASE_URL + "/products/product-catalog/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Reduced Filters (language removed)
job_families = list(range(1, 7))      
job_levels = list(range(1, 11))       
industries = list(range(1, 9))        
job_categories = list(range(1, 24))     

results = []

def get_full_url(relative_link):
    return BASE_URL + relative_link if relative_link.startswith("/") else relative_link

def extract_details_from_link(link):
    try:
        res = requests.get(link, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        sections = []
        for h4_tag in soup.find_all('h4'):
            next_p = h4_tag.find_next_sibling('p')
            if next_p:
                sections.append({
                    "heading": h4_tag.text.strip(),
                    "text": next_p.text.strip()
                })

        description_block = soup.find("meta", {"name": "description"})
        description = description_block['content'] if description_block else ""

        return {"description": description, "sections": sections}
    except Exception as e:
        return {"description": "", "sections": [], "error": str(e)}

def parse_product_row(row, product_type, job_family=None, job_level=None, industry=None, job_category=None):
    title_td = row.find("td", class_="custom__table-heading__title")
    if not title_td:
        return None
    
    link_tag = title_td.find("a")
    if not link_tag:
        return None

    link = get_full_url(link_tag['href'].strip())
    name = link_tag.text.strip()

    columns = row.find_all("td", class_="custom__table-heading__general")
    remote_testing = '✅' if columns[0].find("span", class_="-yes") else '✗'
    adaptive = '✅' if columns[1].find("span", class_="-yes") else '✗'
    test_types = [span.text.strip() for span in columns[2].find_all("span", class_="product-catalogue__key")]

    detail_data = extract_details_from_link(link)

    return {
        "Product Type": product_type,
        "Name": name,
        "Link": link,
        "Remote Testing": remote_testing,
        "Adaptive": adaptive,
        "Test Types": test_types,
        "Description": detail_data.get("description", ""),
        "Sections": detail_data.get("sections", []),
        "Job Family": job_family,
        "Job Level": job_level,
        "Industry": industry,
        "Job Category": job_category
    }

def scrape_combination(combo):
    job_family, job_level, industry = combo
    params = {
        "job_family": job_family,
        "job_level": job_level,
        "industry": industry,
        "action_doFilteringForm": "Search",
        "f": "1"
    }
    try:
        res = requests.get(CATALOG_URL, headers=HEADERS, params=params, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tables = soup.find_all("tr", attrs={"data-course-id": True}) + soup.find_all("tr", attrs={"data-entity-id": True})

        local_results = []
        for row in tables:
            product_type = "Pre-packaged" if row.has_attr("data-course-id") else "Individual"
            parsed = parse_product_row(row, product_type, job_family, job_level, industry)
            if parsed:
                local_results.append(parsed)
        return local_results
    except Exception as e:
        return []

def scrape_job_category(jc):
    params = {
        "job_category": jc,
        "action_doFilteringForm": "Search",
        "f": "1"
    }
    try:
        res = requests.get(CATALOG_URL, headers=HEADERS, params=params, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tables = soup.find_all("tr", attrs={"data-course-id": True}) + soup.find_all("tr", attrs={"data-entity-id": True})

        local_results = []
        for row in tables:
            product_type = "Pre-packaged" if row.has_attr("data-course-id") else "Individual"
            parsed = parse_product_row(row, product_type, job_category=jc)
            if parsed:
                local_results.append(parsed)
        return local_results
    except Exception as e:
        return []

# --- MULTITHREADED RUN ---
start_time = time.time()
combinations = list(product(job_families, job_levels, industries))
print(f"🔄 Scraping {len(combinations)} combinations...")

with ThreadPoolExecutor(max_workers=20) as executor:
    future_to_combo = {executor.submit(scrape_combination, combo): combo for combo in combinations}
    for future in tqdm(as_completed(future_to_combo), total=len(future_to_combo), desc="🔍 Scraping Filters"):
        try:
            res = future.result()
            results.extend(res)
            logging.info(f"✔️ Scraped combo result with {len(res)} products.")
        except Exception as e:
            logging.error(f"❌ Error in combo: {str(e)}")


print(f"🔄 Scraping {len(job_categories)} job categories...")

with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_jc = {executor.submit(scrape_job_category, jc): jc for jc in job_categories}
    for future in tqdm(as_completed(future_to_jc), total=len(future_to_jc), desc="🔍 Scraping Job Categories"):
        try:
            res = future.result()
            results.extend(res)
            logging.info(f"✔️ Scraped job category with {len(res)} products.")
        except Exception as e:
            logging.error(f"❌ Error in job category: {str(e)}")


# --- Save ---
df = pd.DataFrame(results)
df.to_csv("shl_products_detailed.csv", index=False)
with open("shl_products_detailed.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

end_time = time.time()
print(f"✅ Done. Total time: {round(end_time - start_time, 2)} seconds")
