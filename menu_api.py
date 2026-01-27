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
from datetime import datetime, timedelta

# Clover PRODUCTION Credentials
MERCHANT_ID = os.getenv('MERCHANT_ID', 'FFW0J7HB213K1')
CLOVER_TOKEN = os.getenv('CLOVER_TOKEN', '6416e29c-bc22-6d8c-1f62-14e77cbbb914')
CLOVER_BASE_URL = os.getenv('CLOVER_BASE_URL', 'https://api.clover.com')
PORT = int(os.getenv('PORT', 8000))

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
        """Refresh menu from Clover on EVERY request - Always fresh data"""
        # Always fetch fresh data (removed 30-minute cache)
        print(f'🔄 Fetching fresh menu from Clover...')
        
        try:
            all_items = []
            offset = 0
            limit = 100
            
            # Fetch all pages
            while True:
                url = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items?limit={limit}&offset={offset}'
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
            
            # Process all items
            self.menu_cache = []
            seen_ids = set()
            
            for item in all_items:
                item_id = item.get('id')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    self.menu_cache.append({
                        'name': item.get('name'),
                        'price': item.get('price', 0) / 100,
                        'category': item.get('category', {}).get('name', 'General'),
                        'available': not item.get('hidden', False)
                    })
            
            self.last_refresh = datetime.now()
            print(f'✅ Menu refreshed: {len(self.menu_cache)} items at {self.last_refresh.strftime("%H:%M:%S")}')
            return True
            
        except Exception as e:
            print(f'❌ Error refreshing menu: {e}')
            return False
    
    def get_menu(self):
        """Get menu and auto-refresh if needed"""
        self.refresh_menu()
        return sorted(self.menu_cache, key=lambda x: (x['category'], x['name']))


menu = MenuManager()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        'service': 'Aroma Restaurant - Menu API',
        'purpose': 'Provides real-time menu data to ElevenLabs',
        'version': '2.0',
        'environment': 'PRODUCTION',
        'refresh_policy': 'Real-time - Menu fetched fresh on every request',
        'endpoints': {
            'menu_json': '/menu - JSON format (recommended)',
            'menu_text': '/menu/text - Plain text format',
            'refresh': '/menu/refresh - Force refresh (same as accessing /menu)',
            'health': '/health - Service health check'
        },
        'elevenlabs_setup': 'Use /menu endpoint in ElevenLabs Knowledge Base'
    }


@app.get("/menu")
async def get_menu_json():
    """
    🎯 PRIMARY ENDPOINT FOR ELEVENLABS
    Returns current menu in JSON format
    """
    items = menu.get_menu()
    
    # Group by category
    categories = {}
    for item in items:
        cat = item['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'name': item['name'],
            'price': f"${item['price']:.2f}",
            'available': '✓' if item['available'] else '✗'
        })
    
    return {
        'restaurant': 'Aroma Indian Restaurant',
        'last_updated': menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown',
        'total_items': len(items),
        'categories': categories
    }


@app.get("/menu/text", response_class=PlainTextResponse)
async def get_menu_text():
    """
    Alternative: Plain text format
    Use if ElevenLabs prefers text over JSON
    """
    items = menu.get_menu()
    
    # Group by category
    categories = {}
    for item in items:
        cat = item['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    
    text = "AROMA INDIAN RESTAURANT MENU\n"
    text += "=" * 60 + "\n"
    text += f"Updated: {menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown'}\n"
    text += f"Total Items: {len(items)}\n"
    text += "=" * 60 + "\n\n"
    
    for category, cat_items in sorted(categories.items()):
        text += f"\n{category.upper()}\n"
        text += "-" * 60 + "\n"
        for item in cat_items:
            status = "✓" if item['available'] else "✗"
            text += f"{status} {item['name']:<45} ${item['price']:>6.2f}\n"
    
    text += "\n" + "=" * 60 + "\n"
    text += "Menu automatically syncs on every request\n"
    
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


if __name__ == '__main__':
    import uvicorn
    print('\n' + '='*60)
    print('🍽️  Aroma Restaurant - Menu API (PRODUCTION)')
    print('='*60)
    print('📋 Purpose: Serve menu to ElevenLabs Knowledge Base')
    print('🔄 Refresh Policy: REAL-TIME (every request)')
    print('🎯 Use this URL in ElevenLabs: /menu')
    print('🏪 Environment: PRODUCTION')
    print('⚠️  Using LIVE Clover data')
    print('='*60 + '\n')
    uvicorn.run(app, host='0.0.0.0', port=PORT)
