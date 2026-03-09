#!/usr/bin/env python3
"""
Menu API for ElevenLabs - Aroma Indian Restaurant
PRODUCTION VERSION with Dynamic Prompt Injection Support

Endpoints:
  GET /              - Service info
  GET /menu          - Full menu as JSON
  GET /menu/text     - Plain text (ElevenLabs Knowledge Base format)
  GET /menu/prompt   - Compact format for system prompt injection (USE THIS)
  GET /menu/refresh  - Force refresh from Clover
  POST /menu/refresh - Force refresh from Clover
  GET /health        - Health check
  GET /debug/categories   - See all Clover categories
  GET /debug/sample-items - See sample item structure
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
import requests
import os
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# Clover PRODUCTION Credentials
# ─────────────────────────────────────────────
MERCHANT_ID    = os.getenv('MERCHANT_ID',    'FFW0J7HB213K1')
CLOVER_TOKEN   = os.getenv('CLOVER_TOKEN',   '6416e29c-bc22-6d8c-1f62-14e77cbbb914')
CLOVER_BASE_URL = os.getenv('CLOVER_BASE_URL', 'https://api.clover.com')
PORT           = int(os.getenv('PORT', 8000))

# ─────────────────────────────────────────────
# Whitelisted Category IDs (only these appear in menu)
# ─────────────────────────────────────────────
INCLUDED_CATEGORY_IDS = [
    "M17PNQEPG6K02",  # Soups & Sides
    "FY9BQPAQ0NNFP",  # Appetizers-Vegetarian
    "E5H1DFT9T32VR",  # Appetizers-Non Vegetarian
    "FT8HR9VNRQW4R",  # Dosa Specials
    "MEM5GGGW27WX2",  # Vegetable Entrees
    "FSXP785519PBA",  # Chicken Entrees
    "X146DX02VVMG2",  # Seafood Entrees
    "07FG0SA6FMFFY",  # Lamb & Goat Entrees
    "JB8VSZRM49J9P",  # Egg Specials
    "Z1ZKCQTDR6BKJ",  # Aroma Specials
    "EEZHPBVTD0H7W",  # Hyderabad Chef Specials
    "M1H649PKCZ5TE",  # Tandoori & Kebabs
    "RHV2MKASX5FVA",  # Biryani Specials
    "JVKES871M1PX0",  # Indian Breads
    "D191C2W2SYCW0",  # Rice Specials
    "994Q0TTW39AHY",  # Indo Chinese
    "407WNKVYVHS2E",  # Thali's
    "KWZCZRAK0ZE7J",  # Desserts
    "25NPKW5MTBQPA",  # Soda / Cool Drinks / Hot Drinks
]

# ─────────────────────────────────────────────
# Hardcoded items to ALWAYS include regardless of category
# ─────────────────────────────────────────────
ALWAYS_INCLUDE_ITEMS = [
    {
        "id":            "6QSQCJWTRBXZY",
        "name":          "Beef Ullarthu",
        "price":         22.00,
        "category":      "Lamb & Goat Entrees",
        "description":   "",
        "alternateName": "",
        "code":          "",
        "sku":           "",
        "available":     True
    }
]

# ─────────────────────────────────────────────
app = FastAPI(title="Aroma Menu API - For ElevenLabs")
# ─────────────────────────────────────────────


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
        """Refresh menu from Clover - cached for 30 minutes unless forced."""
        if not force and self.last_refresh:
            age = datetime.now() - self.last_refresh
            if age < timedelta(minutes=30):
                print(f'✓ Using cached menu ({int(age.total_seconds() / 60)} min old)')
                return True

        print('🔄 Fetching fresh menu from Clover...')
        try:
            all_items = []
            offset, limit = 0, 200

            while True:
                url = (
                    f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items'
                    f'?expand=categories&limit={limit}&offset={offset}'
                )
                resp = requests.get(url, headers=self.headers, timeout=10)
                resp.raise_for_status()
                items = resp.json().get('elements', [])
                if not items:
                    break
                all_items.extend(items)
                print(f'📥 Fetched {len(items)} items (offset {offset})')
                if len(items) < limit:
                    break
                offset += limit

            self.menu_cache = []
            seen_ids = set()
            skipped_zero = skipped_whitelist = 0

            # ── Always-include hardcoded items first ──
            for forced_item in ALWAYS_INCLUDE_ITEMS:
                seen_ids.add(forced_item['id'])
                self.menu_cache.append({
                    'name':          forced_item['name'],
                    'price':         forced_item['price'],
                    'category':      forced_item['category'],
                    'description':   forced_item['description'],
                    'alternateName': forced_item['alternateName'],
                    'code':          forced_item['code'],
                    'sku':           forced_item['sku'],
                    'available':     forced_item['available']
                })
                print(f'📌 Force-included: {forced_item["name"]}')

            # ── Normal Clover items ──
            for item in all_items:
                item_id     = item.get('id')
                price_cents = item.get('price', 0)
                price       = price_cents / 100

                # Resolve category
                categories_data = item.get('categories', {})
                category_name   = 'General'
                item_included   = False

                if isinstance(categories_data, dict):
                    for cat in categories_data.get('elements', []):
                        if isinstance(cat, dict) and cat.get('id') in INCLUDED_CATEGORY_IDS:
                            category_name = cat.get('name', 'General')
                            item_included = True
                            break

                if not item_included:
                    skipped_whitelist += 1
                    continue

                if price_cents == 0:
                    skipped_zero += 1
                    continue

                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    self.menu_cache.append({
                        'name':          item.get('name', ''),
                        'price':         price,
                        'category':      category_name,
                        'description':   item.get('description', '') or '',
                        'alternateName': item.get('alternateName', '') or '',
                        'code':          item.get('code', '') or '',
                        'sku':           item.get('sku', '') or '',
                        'available':     not item.get('hidden', False)
                    })

            print(f'⏭️  Skipped {skipped_zero} $0 items, {skipped_whitelist} non-whitelisted')
            self.last_refresh = datetime.now()
            print(f'✅ {len(self.menu_cache)} items cached at {self.last_refresh.strftime("%H:%M:%S")}')
            return True

        except Exception as e:
            print(f'❌ Error refreshing menu: {e}')
            return False

    def get_menu(self):
        """Return sorted menu, auto-refreshing if cache is stale."""
        self.refresh_menu()
        return sorted(self.menu_cache, key=lambda x: (x['category'], x['name']))

    def grouped_by_category(self):
        """Return menu items grouped into a dict keyed by category name."""
        categories = {}
        for item in self.get_menu():
            cat = item['category']
            categories.setdefault(cat, []).append(item)
        return categories


menu = MenuManager()


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        'service':        'Aroma Restaurant - Menu API',
        'version':        '3.0',
        'environment':    'PRODUCTION',
        'refresh_policy': '30-minute cache, auto-refresh from Clover',
        'endpoints': {
            '/menu/prompt': '🎯 USE THIS for ElevenLabs system prompt injection',
            '/menu/text':   'Plain text for knowledge base (fallback)',
            '/menu':        'Full JSON menu',
            '/menu/refresh':'Force refresh from Clover',
            '/health':      'Health check',
        }
    }


@app.get("/menu", response_class=JSONResponse)
async def get_menu_json():
    """Full menu as JSON, grouped by category."""
    cats = menu.grouped_by_category()
    structure = []
    for cat_name in sorted(cats.keys()):
        structure.append({
            'category_name': cat_name,
            'items': [
                {
                    'name':          i['name'],
                    'alternateName': i.get('alternateName', ''),
                    'price':         f"${i['price']:.2f}",
                    'description':   i.get('description', ''),
                    'available':     i['available']
                }
                for i in cats[cat_name]
            ]
        })

    return {
        'restaurant':   'Aroma Indian Restaurant',
        'last_updated': menu.last_refresh.strftime('%Y-%m-%d %H:%M:%S') if menu.last_refresh else 'Unknown',
        'total_items':  len(menu.menu_cache),
        'total_categories': len(cats),
        'menu':         structure
    }


@app.get("/menu/text", response_class=PlainTextResponse)
async def get_menu_text():
    """
    Plain text menu — original format used by ElevenLabs knowledge base.
    Still available as fallback, but /menu/prompt is preferred.
    """
    cats  = menu.grouped_by_category()
    lines = ["AROMA INDIAN RESTAURANT - MENU", "=" * 60, ""]

    for category in sorted(cats.keys()):
        lines.append(category)
        lines.append("-" * 60)
        for item in cats[category]:
            suffix = "" if item['available'] else " (Currently Unavailable)"
            line   = f"  {item['name']}: ${item['price']:.2f}{suffix}"
            if item.get('alternateName'):
                line += f" (Also known as: {item['alternateName']})"
            lines.append(line)
            if item.get('description'):
                lines.append(f"    {item['description']}")
        lines.append("")

    lines += [
        "=" * 60,
        f"Total Categories: {len(cats)}",
        f"Total Items: {len(menu.menu_cache)}",
        f"Last Updated: {menu.last_refresh.strftime('%B %d, %Y at %I:%M %p') if menu.last_refresh else 'Recently'}"
    ]
    return "\n".join(lines)


@app.get("/menu/prompt", response_class=PlainTextResponse)
async def get_menu_for_prompt():
    """
    🎯 OPTIMIZED FOR ELEVENLABS SYSTEM PROMPT INJECTION

    Fetch this endpoint BEFORE each call and append the result to your
    system prompt. This guarantees the agent only knows today's live menu
    and cannot hallucinate items that don't exist.

    Usage in your ElevenLabs call handler:
        menu_text = requests.get('https://aromamenu-km87.onrender.com/menu/prompt').text
        full_prompt = base_system_prompt + menu_text
        # Pass full_prompt as conversation_config_override > agent > prompt > prompt
    """
    cats  = menu.grouped_by_category()
    ts    = menu.last_refresh.strftime('%Y-%m-%d %H:%M') if menu.last_refresh else 'recently'

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║        AROMA LIVE MENU — TODAY'S ONLY VALID ITEMS        ║",
       f"║        Last synced from Clover: {ts:<26}║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "STRICT RULES FOR THE AGENT:",
        "1. You may ONLY offer, confirm, or discuss items listed below.",
        "2. If a customer requests an item NOT in this list, respond:",
        '   "I\'m sorry, we don\'t have that available today.',
        '    Can I help you with something else from our menu?"',
        "3. NEVER invent, guess, or suggest items absent from this list.",
        "4. Item availability marked (UNAVAILABLE) must not be offered.",
        "",
    ]

    for category in sorted(cats.keys()):
        lines.append(f"── {category} ──")
        for item in cats[category]:
            if item['available']:
                lines.append(f"  • {item['name']} — ${item['price']:.2f}")
            else:
                lines.append(f"  • {item['name']} — ${item['price']:.2f}  [NOT AVAILABLE TODAY]")
        lines.append("")

    lines += [
        "══════════════════════════════════════════════════════════",
        f"Total items today: {len(menu.menu_cache)}",
        "END OF LIVE MENU — Do not offer anything outside this list.",
        "══════════════════════════════════════════════════════════",
    ]

    return "\n".join(lines)


@app.get("/menu/refresh")
@app.post("/menu/refresh")
async def refresh_menu_endpoint():
    """Force immediate menu refresh from Clover (GET or POST)."""
    success = menu.refresh_menu(force=True)
    return {
        'success':  success,
        'items':    len(menu.menu_cache),
        'updated':  menu.last_refresh.isoformat() if menu.last_refresh else None,
        'message':  f'Menu refreshed! Now showing {len(menu.menu_cache)} items.'
    }


@app.get("/health")
async def health():
    age_minutes = None
    if menu.last_refresh:
        age_minutes = int((datetime.now() - menu.last_refresh).total_seconds() / 60)
    return {
        'status':       'healthy',
        'environment':  'PRODUCTION',
        'items':        len(menu.menu_cache),
        'last_refresh': menu.last_refresh.isoformat() if menu.last_refresh else None,
        'cache_age_minutes': age_minutes
    }


@app.get("/debug/categories")
async def debug_categories():
    """Show all categories from Clover and whether they're whitelisted."""
    try:
        url  = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/categories'
        resp = requests.get(url, headers=menu.headers, timeout=10)
        resp.raise_for_status()
        cats = resp.json().get('elements', [])
        return {
            'total_categories': len(cats),
            'categories': [
                {
                    'id':           c.get('id'),
                    'name':         c.get('name'),
                    'in_whitelist': c.get('id') in INCLUDED_CATEGORY_IDS
                }
                for c in cats
            ]
        }
    except Exception as e:
        return {'error': str(e)}


@app.get("/debug/sample-items")
async def debug_sample_items():
    """Show 5 sample items with their raw Clover category structure."""
    try:
        url  = f'{CLOVER_BASE_URL}/v3/merchants/{MERCHANT_ID}/items?expand=categories&limit=5'
        resp = requests.get(url, headers=menu.headers, timeout=10)
        resp.raise_for_status()
        return {
            'sample_items': [
                {
                    'name':          i.get('name'),
                    'price_cents':   i.get('price'),
                    'categories_raw': i.get('categories')
                }
                for i in resp.json().get('elements', [])
            ]
        }
    except Exception as e:
        return {'error': str(e)}


# ─────────────────────────────────────────────
if __name__ == '__main__':
    import uvicorn
    print('\n' + '=' * 60)
    print('🍽️   Aroma Restaurant - Menu API v3.0 (PRODUCTION)')
    print('=' * 60)
    print('🎯  NEW: /menu/prompt  — inject live menu into ElevenLabs system prompt')
    print('📋  /menu/text         — plain text for knowledge base (fallback)')
    print('📦  /menu              — full JSON')
    print('🔄  /menu/refresh      — force Clover sync')
    print('🏥  /health            — health check')
    print('🔍  /debug/categories  — inspect Clover categories')
    print('=' * 60)
    print('⚡  Cache: 30 minutes | Filtering: whitelisted categories only')
    print('💲  $0 price items excluded automatically')
    print('=' * 60 + '\n')
    uvicorn.run(app, host='0.0.0.0', port=PORT)
