import os
import json
import threading
import re
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# .env
JSON_FILE_PATH = "shl_products_detailed.json"
CHAT_MODEL = "gemini-1.5-flash"  
DEBUG = True

# Load API key
load_dotenv()
GOOGLE_API_KEY = st.secrets("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError("Set GOOGLE_API_KEY in your environment")

# Helper Functions
def _debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

# Thread-safe loading of products
_products_lock = threading.Lock()
_products_data = None

def _get_products():
    global _products_data
    with _products_lock:
        if _products_data is None:
            with open(JSON_FILE_PATH, encoding="utf-8") as f:
                _products_data = json.load(f)
    return _products_data

def _get_product_text(product):
    """Convert a product to a string representation"""
    text = f"Name: {product['Name']}\n"
    text += f"Description: {product['Description']}\n"
    
    for section in product.get('Sections', []):
        heading = section.get('heading', '')
        content = section.get('text', '')
        if heading and content:
            text += f"{heading}: {content}\n"
    
    return text

def _extract_duration(product):
    """Extract assessment duration in minutes"""
    for section in product.get('Sections', []):
        if section.get('heading') == 'Assessment length':
            text = section.get('text', '')
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
    return 60  # Default duration if not found

def _extract_test_types(product):
    """Extract test types"""
    if "Test Types" in product and product["Test Types"]:
        return product["Test Types"]
    return ["Knowledge & Skills"]  # Default

def _format_for_llm(products, limit=30):
    """Format products for LLM input, respecting context limits"""
    formatted = []
    for i, product in enumerate(products[:limit]):
        formatted.append(f"PRODUCT {i+1}:\n{_get_product_text(product)}\nLink: {product['Link']}\n")
    return "\n".join(formatted)


# Enhanced product extraction for API format
def _extract_product_api_format(product):
    """Extract product information in the format required for the API"""
    return {
        "url": product.get("Link", ""),
        "adaptive_support": "Yes" if product.get("Adaptive") == "Yes" else "No",
        "description": product.get("Description", ""),
        "duration": _extract_duration(product),
        "remote_support": "Yes" if product.get("Remote Testing") == "Yes" else "No",
        "test_type": _extract_test_types(product)
    }

# Main recommendation functions
def recommend_assessment(user_query: str, k: int = 5) -> str:
    """
    Return assessments matching user query as JSON string by directly asking the LLM
    Traditional format for Streamlit UI: [{"name": "...", "url": "..."}]
    """
    _debug_print(f"\n\n=== Processing query: {user_query} ===")
    
    # Get all products
    products = _get_products()
    _debug_print(f"Loaded {len(products)} products from knowledge base")
    
    # Make sure we don't overwhelm the context window
    # IMPORTANT: Randomize products to prevent the same results each time
    import random
    sample_size = min(50, len(products))
    sampled_products = random.sample(products, sample_size)
    
    # Format the products for the LLM
    products_text = _format_for_llm(sampled_products)
    
    # Create the prompt
    prompt = f"""You are an AI assistant for SHL, a company that offers various assessments for hiring and employee development.

TASK: Based on the user query, identify the {k} most relevant assessment products from the list below.

USER QUERY: "{user_query}"

AVAILABLE ASSESSMENTS:
{products_text}

Select the {k} most relevant assessments that match the user's needs, considering:
1. Job role/industry mentioned in the query
2. Skills being assessed
3. Time constraints mentioned
4. Experience level requirements

RESPOND ONLY with a valid format array containing the selected assessments in this exact format:
[
  {{"name": "Assessment Name 1", "url": "https://link-to-assessment-1"}},
  {{"name": "Assessment Name 2", "url": "https://link-to-assessment-2"}},
  ...
]

Each assessment must have only these two fields: "name" and "url".
Do not include any other fields or commentary or tags or even tags' syntax and symbols.
"""

    try:
        # Call the LLM 
        llm = ChatGoogleGenerativeAI(
            model=CHAT_MODEL, 
            google_api_key=GOOGLE_API_KEY,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        response = llm.invoke(prompt)
        response_text = str(response.content).strip()
        
        # Extract just the JSON part
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            # Parse and validate
            results = json.loads(json_str)
            
            # Ensure each item has exactly 'name' and 'url' fields
            clean_results = []
            for item in results:
                if 'name' in item and 'url' in item:
                    clean_results.append({
                        "name": item["name"],
                        "url": item["url"]
                    })
            
            # Return the validated JSON
            return json.dumps(clean_results, ensure_ascii=False)
        else:
            _debug_print("No valid JSON found in LLM response")
            _debug_print(f"Raw response: {response_text}")
            # Return fallback
            return json.dumps([{
                "name": "No suitable assessments found",
                "url": "https://www.shl.com/contact-us/"
            }])
            
    except Exception as e:
        _debug_print(f"Error in LLM recommendation: {e}")
        _debug_print(f"Response: {response_text if 'response_text' in locals() else 'No response'}")
        # Return fallback
        return json.dumps([{
            "name": "Error retrieving recommendations",
            "url": "https://www.shl.com/contact-us/"
        }])
    
    # Add this function to your analysis_engine.py file:

def recommend_assessment_api_format(user_query: str, k: int = 5) -> dict:
    """
    Return assessments in the API-required format with expanded fields
    Format: {"recommended_assessments": [{url, adaptive_support, description, duration, remote_support, test_type},...]}
    """
    _debug_print(f"\n\n=== Processing API query: {user_query} ===")
    
    # Get all products
    products = _get_products()
    _debug_print(f"Loaded {len(products)} products from knowledge base")
    
    # IMPORTANT: Randomize the order of products to prevent bias
    import random
    sampled_products = random.sample(products, min(50, len(products)))
    
    # Format products for the LLM
    products_text = _format_for_llm(sampled_products)
    
    # Prompt for API recommendations
    prompt = f"""You are an SHL assessment recommendation expert.

USER QUERY: "{user_query}"

TASK: Review the assessments below and select EXACTLY {k} assessments that best match this query.

AVAILABLE ASSESSMENTS:
{products_text}

SELECTION CRITERIA:
1. Match assessment content to skills/topics in the query (highest priority)
2. Match assessment to job role or industry if mentioned
3. Consider experience level requirements if mentioned
4. Consider time constraints if mentioned

For programming or technical assessments, match the EXACT language or technology mentioned.

INSTRUCTIONS:
1. Analyze what the user is looking for
2. For each assessment, evaluate relevance to the query
3. Select the {k} most relevant assessments
4. Output ONLY their NUMBERS (separated by commas)

For example, if assessments 7, 12, 15, 22, and 31 are most relevant, respond ONLY with:
7, 12, 15, 22, 31

IMPORTANT: DO NOT include any explanations, just the assessment numbers.
"""

    try:
        # Call the LLM 
        llm = ChatGoogleGenerativeAI(
            model=CHAT_MODEL, 
            google_api_key=GOOGLE_API_KEY,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        response = llm.invoke(prompt)
        response_text = str(response.content).strip()
        
        _debug_print(f"LLM Response: {response_text}")
        
        # Extract assessment indices 
        indices = []
        # Look for numbers in the response
        import re
        matches = re.findall(r'\b(\d+)\b', response_text)
        
        for match in matches:
            try:
                idx = int(match) - 1  
                if 0 <= idx < len(sampled_products):
                    indices.append(idx)
            except ValueError:
                continue
        
        # Limit to k assessments
        indices = indices[:k]
        
        # If no valid indices found, use a fallback
        if not indices:
            _debug_print("No valid indices found, using fallback")
            # Use first k products as fallback
            indices = list(range(min(k, len(sampled_products))))
        
        _debug_print(f"Selected indices: {indices}")
        
        # API response according to the instructed format ({"recommended_assessments": [...]})
        recommended_assessments = []
        for idx in indices:
            product = sampled_products[idx]
            
            assessment = {
                "url": product.get("Link", ""),
                "adaptive_support": "Yes" if product.get("Adaptive") == "Yes" else "No",
                "description": product.get("Description", ""),
                "duration": _extract_duration(product),
                "remote_support": "Yes" if product.get("Remote Testing") == "Yes" else "No",
                "test_type": _extract_test_types(product)
            }
            recommended_assessments.append(assessment)
        
        # Return FORMAT
        return {"recommended_assessments": recommended_assessments}
            
    except Exception as e:
        _debug_print(f"Error in API recommendation: {e}")
        import traceback
        _debug_print(traceback.format_exc())
        
        # Return error in the expected format
        return {"recommended_assessments": [{
            "url": "https://www.shl.com/contact-us/",
            "adaptive_support": "No",
            "description": f"Error retrieving recommendations: {str(e)}",
            "duration": 60,
            "remote_support": "Yes",
            "test_type": ["Error"]
        }]}
