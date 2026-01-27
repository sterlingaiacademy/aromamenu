#!/usr/bin/env python3
"""
Simple Menu API for ElevenLabs Knowledge Base
Aroma Indian Restaurant
This is a lightweight API that only serves menu data to ElevenLabs
With 30-minute caching for optimal performance
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
import requests
import os
from datetime import datetime, timedelta

# Clover Production Credentials
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
        self.cache_duration = timedelta(minutes=30)
        self.refresh_menu()
    
    def should_refresh(self):
        """Check if cache is stale (older than 30 minutes)"""
        if not self.last_refresh:
            return True
        time_since_refresh = datetime.now() - self.last_refresh
        is_stale = time_since_refresh > self.cache_duration
        
        if is_stale:
            minutes_old = int(time_since_refresh.total_seconds() / 60)
            print(f'⏰ Cache is {minutes_old} minutes old - refreshing...')
        
        return is_stale
    
    def refresh_menu(self, force=False):
        """
        Refresh menu from Clover
        - force=False: Only refresh if cache is stale (30+ minutes old)
        - force=True: Always refresh immediately
        """
        # Check if we should refresh
        if not force and not self.should_refresh():
            minutes_old = int((datetime.now() - self.last_refresh).total_seconds() / 60)
            print(f'✅ Using cached menu ({len(self.menu_cache)} items, cached {minutes_old} min ago)')
            return True
        
        print(f'🔄 Fetching fresh menu from Clover (200 items expected)...')
        
        try:
            all_items = []
            offset = 0
            limit = 100
            request_count = 0
            
            # Fetch all pages (for 200 items, this will be 2 requests)
            while True:
                request_count += 1
                url = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items?limit={limit}&offset={offset}'
                print(f'   📡 Request #{request_count}: Fetching items {offset}-{offset + limit - 1}...')
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                items = data.get('elements', [])
                
                if not items:
                    print(f'   ✓ No more items found')
                    break
                
                all_items.extend(items)
                print(f'   ✓ Got {len(items)} items (total so far: {len(all_items)})')
                
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
            print(f'✅ Menu refreshed successfully: {len(self.menu_cache)} items')
            print(f'   ⏱️  Next auto-refresh in: 30 minutes (at {(self.last_refresh + self.cache_duration).strftime("%H:%M:%S")})')
            return True
            
        except Exception as e:
            print(f'❌ Error refreshing menu: {e}')
            print(f'⚠️  Keeping cached menu ({len(self.menu_cache)} items) until next refresh attempt')
            return False
    
    def get_menu(self):
        """Get menu - uses cache if fresh, otherwise refreshes"""
        self.refresh_menu()
        return sorted(self.menu_cache, key=lambda x: (x['category'], x['name']))
    
    def get_cache_status(self):
        """Get cache status info"""
        if not self.last_refresh:
            return {
                'cached': False,
                'items': 0,
                'last_refresh': None,
                'next_refresh': None,
                'cache_age_seconds': None
            }
        
        now = datetime.now()
        cache_age = now - self.last_refresh
        next_refresh = self.last_refresh + self.cache_duration
        
        return {
            'cached': True,
            'items': len(self.menu_cache),
            'last_refresh': self.last_refresh.strftime('%Y-%m-%d %H:%M:%S'),
            'next_refresh': next_refresh.strftime('%Y-%m-%d %H:%M:%S'),
            'cache_age_seconds': int(cache_age.total_seconds()),
            'cache_age_minutes': int(cache_age.total_seconds() / 60),
            'is_fresh': cache_age < self.cache_duration
        }


menu = MenuManager()


@app.get("/")
async def root():
    """Root endpoint - API information"""
    cache_status = menu.get_cache_status()
    return {
        'service': 'Aroma Restaurant - Menu API',
        'purpose': 'Provides real-time menu data to ElevenLabs',
        'version': '2.1',
        'environment': 'PRODUCTION',
        'total_items': len(menu.menu_cache),
        'refresh_policy': 'Auto-refresh every 30 minutes (or force refresh anytime)',
        'cache_status': cache_status,
        'endpoints': {
            'menu_json': '/menu - JSON format (recommended for ElevenLabs)',
            'menu_text': '/menu/text - Plain text format',
            'refresh': '/menu/refresh - Force refresh immediately',
            'cache_status': '/cache-status - View cache details',
            'health': '/health - Service health check'
        },
        'elevenlabs_setup': 'Use /menu endpoint in ElevenLabs Knowledge Base'
    }


@app.get("/menu")
async def get_menu_json():
    """
    🎯 PRIMARY ENDPOINT FOR ELEVENLABS
    Returns current menu in JSON format
    Uses 30-minute cache - auto-refreshes if stale
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
    
    cache_status = menu.get_cache_status()
    
    return {
        'restaurant': 'Aroma Indian Restaurant',
        'environment': 'PRODUCTION',
        'last_updated': menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown',
        'total_items': len(items),
        'cache_info': {
            'is_fresh': cache_status['is_fresh'],
            'cache_age_minutes': cache_status['cache_age_minutes'],
            'next_auto_refresh': cache_status['next_refresh']
        },
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
    
    cache_status = menu.get_cache_status()
    cache_info = f"Cached {cache_status['cache_age_minutes']} minutes ago" if cache_status['cached'] else "No cache"
    
    text = "AROMA INDIAN RESTAURANT MENU\n"
    text += "=" * 60 + "\n"
    text += f"Updated: {menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown'}\n"
    text += f"Cache Status: {cache_info}\n"
    text += f"Total Items: {len(items)}\n"
    text += "=" * 60 + "\n\n"
    
    for category, cat_items in sorted(categories.items()):
        text += f"\n{category.upper()}\n"
        text += "-" * 60 + "\n"
        for item in cat_items:
            status = "✓" if item['available'] else "✗"
            text += f"{status} {item['name']:<45} ${item['price']:>6.2f}\n"
    
    text += "\n" + "=" * 60 + "\n"
    text += f"Menu auto-refreshes every 30 minutes\n"
    text += f"Next refresh: {cache_status['next_refresh']}\n"
    
    return text


@app.get("/cache-status")
async def cache_status():
    """
    View detailed cache information
    Useful for monitoring and debugging
    """
    status = menu.get_cache_status()
    return {
        'cache_status': status,
        'message': f"{'Cache is fresh' if status['is_fresh'] else 'Cache is stale - will refresh on next request'}",
        'stats': {
            'total_items_in_menu': len(menu.menu_cache),
            'refresh_interval_minutes': 30,
            'api_calls_saved': f"Estimated {int(status['cache_age_minutes'] / 30)} refresh cycles avoided"
        }
    }


@app.post("/menu/refresh")
async def refresh_menu_manual():
    """Force menu refresh immediately (POST)"""
    print('🔔 Manual refresh requested (POST)')
    success = menu.refresh_menu(force=True)
    cache_status = menu.get_cache_status()
    return {
        'success': success,
        'items': len(menu.menu_cache),
        'updated': menu.last_refresh.isoformat() if menu.last_refresh else None,
        'message': f'{"✅ Menu refreshed successfully" if success else "❌ Error refreshing menu"}',
        'cache_status': cache_status
    }


@app.get("/menu/refresh")
async def refresh_menu_get():
    """Force menu refresh immediately (GET - browser friendly)"""
    print('🔔 Manual refresh requested (GET)')
    success = menu.refresh_menu(force=True)
    cache_status = menu.get_cache_status()
    return {
        'success': success,
        'items': len(menu.menu_cache),
        'updated': menu.last_refresh.isoformat() if menu.last_refresh else None,
        'message': f'{"✅ Menu refreshed! Now showing" if success else "❌ Error refreshing menu"} {len(menu.menu_cache)} items',
        'cache_status': cache_status
    }


@app.get("/health")
async def health():
    """Health check with cache info"""
    cache_status = menu.get_cache_status()
    return {
        'status': 'healthy',
        'environment': 'PRODUCTION',
        'items': len(menu.menu_cache),
        'last_refresh': menu.last_refresh.isoformat() if menu.last_refresh else None,
        'cache_info': cache_status
    }


if __name__ == '__main__':
    import uvicorn
    print('\n' + '='*60)
    print('🍽️  Aroma Restaurant - Menu API (PRODUCTION)')
    print('='*60)
    print('📋 Purpose: Serve menu to ElevenLabs Knowledge Base')
    print('💾 Cache Strategy: 30-minute intelligent caching')
    print('📊 Expected Items: ~200 menu items')
    print('🎯 Primary Endpoint: /menu')
    print('🏪 Environment: PRODUCTION')
    print('='*60 + '\n')
    uvicorn.run(app, host='0.0.0.0', port=PORT)
