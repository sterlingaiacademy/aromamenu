#!/usr/bin/env python3
"""
Simple Menu API for ElevenLabs Knowledge Base
Aroma Indian Restaurant - PRODUCTION
This is a lightweight API that only serves menu data to ElevenLabs
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
import requests
import os
import re
from datetime import datetime, timedelta

# Clover PRODUCTION Credentials
MERCHANT_ID = os.getenv('MERCHANT_ID', 'FFW0J7HB213K1')
CLOVER_TOKEN = os.getenv('CLOVER_TOKEN', '6416e29c-bc22-6d8c-1f62-14e77cbbb914')
CLOVER_BASE_URL = os.getenv('CLOVER_BASE_URL', 'https://api.clover.com')
PORT = int(os.getenv('PORT', 8000))

# ✅ Category IDs to INCLUDE in the menu (WHITELIST ONLY)
INCLUDED_CATEGORY_IDS = [
    "M17PNQEPG6K02",   # Soups & Sides
    "FY9BQPAQ0NNFP",   # Appetizers-Vegetarian
    "E5H1DFT9T32VR",   # Appetizers-Non Vegetarian
    "FT8HR9VNRQW4R",   # Dosa Specials
    "MEM5GGGW27WX2",   # Vegetable Entrees
    "FSXP785519PBA",   # Chicken Entrees
    "X146DX02VVMG2",   # Seafood Entrees
    "07FG0SA6FMFFY",   # Lamb & Goat Entrees
    "JB8VSZRM49J9P",   # Egg Specials
    "Z1ZKCQTDR6BKJ",   # Aroma Specials
    "EEZHPBVTD0H7W",   # Hyderabad Chef Specials
    "M1H649PKCZ5TE",   # Tandoori & Kebabs
    "RHV2MKASX5FVA",   # Biryani Specials
    "JVKES871M1PX0",   # Indian Breads
    "D191C2W2SYCW0",   # Rice Specials
    "994Q0TTW39AHY",   # Indo Chinese
    "407WNKVYVHS2E",   # Thali's
    "KWZCZRAK0ZE7J",   # Desserts
    "25NPKW5MTBQPA",   # Soda / Cool Drinks / Hot Drinks
]

app = FastAPI(title="Aroma Menu API - For ElevenLabs")

class MenuManager:
    def __init__(self):
        self.headers = {
            'Authorization': f'Bearer {CLOVER_TOKEN}',
            'Content-Type': 'application/json'
        }
        self.menu_cache = []
        self.last_refresh = None
        self.refresh_menu()
    
    def refresh_menu(self, force=False):
        """Refresh menu from Clover - cached for 30 minutes unless forced"""
        # Check if we need to refresh (30-minute cache)
        if not force and self.last_refresh:
            time_since_refresh = datetime.now() - self.last_refresh
            if time_since_refresh < timedelta(minutes=30):
                print(f'✓ Using cached menu (refreshed {int(time_since_refresh.total_seconds() / 60)} minutes ago)')
                return True
        
        print(f'🔄 Fetching fresh menu from Clover...')
        
        try:
            all_items = []
            offset = 0
            limit = 200  # Increased limit for better performance with 200+ items
            
            # Fetch all pages with expanded categories
            while True:
                url = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items?expand=categories&limit={limit}&offset={offset}'
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                items = data.get('elements', [])
                
                if not items:
                    break
                
                all_items.extend(items)
                print(f'📥 Fetched {len(items)} items (offset: {offset})')
                
                # Check if there are more items
                if len(items) < limit:
                    break
                
                offset += limit
            
            # Process all items - Filter by whitelist and $0 items
            self.menu_cache = []
            seen_ids = set()
            skipped_zero_price = 0
            skipped_not_in_whitelist = 0
            
            for item in all_items:
                item_id = item.get('id')
                price_cents = item.get('price', 0)
                price_dollars = price_cents / 100
                
                # Get category info - Clover returns categories as {elements: [...]}
                categories_data = item.get('categories', {})
                category_id = None
                category_name = 'General'
                item_included = False
                
                # Clover structure: {"elements": [{"id": "...", "name": "..."}]}
                if isinstance(categories_data, dict) and 'elements' in categories_data:
                    elements = categories_data.get('elements', [])
                    if isinstance(elements, list) and len(elements) > 0:
                        # Check if any category is in whitelist
                        for cat in elements:
                            if isinstance(cat, dict):
                                cat_id = cat.get('id')
                                if cat_id in INCLUDED_CATEGORY_IDS:
                                    category_id = cat_id
                                    category_name = cat.get('name', 'General')
                                    item_included = True
                                    break
                
                # ONLY include items in the whitelist
                if not item_included:
                    skipped_not_in_whitelist += 1
                    continue
                
                # Skip items with $0 price
                if price_cents == 0 or price_dollars == 0:
                    skipped_zero_price += 1
                    continue
                
                # Skip duplicate items
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    
                    # Keep item name exactly as-is from Clover
                    item_name = item.get('name', '')
                    
                    self.menu_cache.append({
                        'name': item_name,
                        'price': price_dollars,
                        'category': category_name,
                        'available': not item.get('hidden', False)
                    })
            
            print(f'⏭️  Skipped {skipped_zero_price} items with $0 price')
            print(f'🎯 Skipped {skipped_not_in_whitelist} items not in whitelist')
            
            self.last_refresh = datetime.now()
            print(f'✅ Menu refreshed: {len(self.menu_cache)} items at {self.last_refresh.strftime("%H:%M:%S")}')
            return True
            
        except Exception as e:
            print(f'❌ Error refreshing menu: {e}')
            return False
    
    def get_menu(self):
        """Get menu - auto-refresh if cache is older than 30 minutes"""
        self.refresh_menu()  # Will use cache if less than 30 minutes old
        return sorted(self.menu_cache, key=lambda x: (x['category'], x['name']))


menu = MenuManager()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        'service': 'Aroma Restaurant - Menu API',
        'purpose': 'Provides real-time menu data to ElevenLabs',
        'version': '2.1',
        'environment': 'PRODUCTION',
        'refresh_policy': '30-minute cache - Menu refreshes automatically every 30 minutes',
        'filtering': f'Showing only {len(INCLUDED_CATEGORY_IDS)} whitelisted categories',
        'endpoints': {
            'menu_text': '/menu/text - Plain text format (🎯 RECOMMENDED FOR ELEVENLABS)',
            'menu_json': '/menu - JSON format with categories',
            'refresh': '/menu/refresh - Force immediate refresh',
            'health': '/health - Service health check'
        },
        'elevenlabs_setup': 'Use /menu/text endpoint in ElevenLabs Knowledge Base for best voice AI results'
    }


@app.get("/menu")
async def get_menu_json():
    """
    🎯 PRIMARY ENDPOINT FOR ELEVENLABS
    Returns current menu organized by categories with items underneath
    """
    items = menu.get_menu()
    
    # Group by category
    categories = {}
    for item in items:
        cat = item['category']
        if cat not in categories:
            categories[cat] = {
                'category_name': cat,
                'items': []
            }
        categories[cat]['items'].append({
            'name': item['name'],
            'price': f"${item['price']:.2f}",
            'available': item['available']
        })
    
    # Convert to list format for better display
    menu_structure = []
    for cat_name in sorted(categories.keys()):
        menu_structure.append(categories[cat_name])
    
    return {
        'restaurant': 'Aroma Indian Restaurant',
        'last_updated': menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown',
        'total_items': len(items),
        'total_categories': len(categories),
        'menu': menu_structure
    }


@app.get("/menu/text", response_class=PlainTextResponse)
async def get_menu_text():
    """
    🎯 OPTIMIZED FOR ELEVENLABS VOICE AI
    Plain text format organized by categories
    """
    items = menu.get_menu()
    
    # Group by category
    categories = {}
    for item in items:
        cat = item['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    
    # Create organized text format
    text = "AROMA INDIAN RESTAURANT - MENU\n"
    text += "=" * 60 + "\n\n"
    
    for category in sorted(categories.keys()):
        text += f"{category}\n"
        text += "-" * 60 + "\n"
        
        cat_items = categories[category]
        for item in cat_items:
            if item['available']:
                text += f"  {item['name']}: ${item['price']:.2f}\n"
            else:
                text += f"  {item['name']}: ${item['price']:.2f} (Currently Unavailable)\n"
        
        text += "\n"
    
    text += "=" * 60 + "\n"
    text += f"Total Categories: {len(categories)}\n"
    text += f"Total Items: {len(items)}\n"
    text += f"Last Updated: {menu.last_refresh.strftime('%B %d, %Y at %I:%M %p') if menu.last_refresh else 'Recently'}\n"
    
    return text


@app.post("/menu/refresh")
async def refresh_menu_manual():
    """Force menu refresh (for testing)"""
    success = menu.refresh_menu(force=True)
    return {
        'success': success,
        'items': len(menu.menu_cache),
        'updated': menu.last_refresh.isoformat() if menu.last_refresh else None
    }


@app.get("/menu/refresh")
async def refresh_menu_get():
    """Force menu refresh via GET (browser-friendly)"""
    success = menu.refresh_menu(force=True)
    return {
        'success': success,
        'items': len(menu.menu_cache),
        'updated': menu.last_refresh.isoformat() if menu.last_refresh else None,
        'message': f'Menu refreshed! Now showing {len(menu.menu_cache)} items.'
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        'status': 'healthy',
        'environment': 'PRODUCTION',
        'items': len(menu.menu_cache),
        'last_refresh': menu.last_refresh.isoformat() if menu.last_refresh else None
    }


@app.get("/debug/categories")
async def debug_categories():
    """Debug endpoint to see all categories from Clover"""
    try:
        url = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/categories'
        headers = {
            'Authorization': f'Bearer {CLOVER_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        categories = data.get('elements', [])
        
        return {
            'total_categories': len(categories),
            'categories': [
                {
                    'id': cat.get('id'),
                    'name': cat.get('name'),
                    'in_whitelist': cat.get('id') in INCLUDED_CATEGORY_IDS
                }
                for cat in categories
            ]
        }
    except Exception as e:
        return {'error': str(e)}


@app.get("/debug/sample-items")
async def debug_sample_items():
    """Debug endpoint to see sample items and their category structure"""
    try:
        url = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items?expand=categories&limit=5'
        headers = {
            'Authorization': f'Bearer {CLOVER_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        items = data.get('elements', [])
        
        return {
            'sample_items': [
                {
                    'name': item.get('name'),
                    'price': item.get('price'),
                    'categories': item.get('categories'),
                    'category_type': str(type(item.get('categories')))
                }
                for item in items
            ]
        }
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    import uvicorn
    print('\n' + '='*60)
    print('🍽️  Aroma Restaurant - Menu API (PRODUCTION)')
    print('='*60)
    print('📋 Purpose: Serve menu to ElevenLabs Knowledge Base')
    print('🔄 Refresh Policy: 30-minute cache (auto-refresh)')
    print('🎯 Use this URL in ElevenLabs: /menu/text')
    print('🏪 Environment: PRODUCTION')
    print('⚠️  Using LIVE Clover data')
    print('💲 Filtering: Items with $0 price are excluded')
    print(f'✅ Whitelist: Only showing {len(INCLUDED_CATEGORY_IDS)} approved categories')
    print('📊 Optimized for 200+ items')
    print('⚡ Fast: Cached responses for better performance')
    print('='*60 + '\n')
    uvicorn.run(app, host='0.0.0.0', port=PORT)
