import os
import time
import requests
from datetime import datetime
import json

# Configuration
TELEGRAM_BOT_TOKEN = "8227029373:AAEnwpYSEl2gf6_KFhNYkXwqoebfp5J97ho"
TELEGRAM_CHAT_ID = "@QuantBotV2"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/"

# Filters (easily adjustable)
MIN_MARKET_CAP = 20000  # $20k
MIN_VOLUME = 20000  # $20k
MAX_MARKET_CAP = 20000000  # $20M

# Track sent tokens to avoid duplicates
sent_tokens = set()
token_call_times = {}

def send_telegram_message(message):
    """Send message to Telegram channel"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def get_solana_tokens():
    """Fetch trending Solana tokens from DexScreener"""
    try:
        # Get trending tokens on Solana
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('pairs', [])
        return []
    except Exception as e:
        print(f"Error fetching tokens: {e}")
        return []

def format_number(num):
    """Format numbers with K, M, B suffixes"""
    if num is None:
        return "N/A"
    
    num = float(num)
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.2f}K"
    else:
        return f"${num:.2f}"

def calculate_top_holders_percentage(token_address):
    """Calculate top 10 holders percentage using Helius API"""
    try:
        # Using Helius API to get token holders
        helius_api_key = "836a3dc9-c051-4074-97a3-36098cd59efe"
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={helius_api_key}"
        
        # For now, return a placeholder since we need specific RPC calls
        # You can enhance this with actual holder data
        return "N/A"
    except:
        return "N/A"

def get_minutes_ago(token_address):
    """Calculate how many minutes ago the token was first called"""
    if token_address in token_call_times:
        time_diff = datetime.now() - token_call_times[token_address]
        return int(time_diff.total_seconds() / 60)
    return 0

def check_and_post_token(pair):
    """Check if token meets criteria and post to Telegram"""
    try:
        # Extract data
        token_address = pair.get('baseToken', {}).get('address')
        token_name = pair.get('baseToken', {}).get('name', 'Unknown')
        token_symbol = pair.get('baseToken', {}).get('symbol', 'Unknown')
        
        # Skip if no address
        if not token_address:
            return
        
        # Skip if already posted
        if token_address in sent_tokens:
            return
        
        # Get metrics
        fdv = pair.get('fdv')
        volume_24h = pair.get('volume', {}).get('h24')
        liquidity = pair.get('liquidity', {}).get('usd', 0)
        
        # Skip if on wrong chain
        if pair.get('chainId') != 'solana':
            return
        
        # Apply filters
        if fdv is None or volume_24h is None:
            return
            
        fdv = float(fdv)
        volume_24h = float(volume_24h)
        
        # Check if meets criteria
        if fdv < MIN_MARKET_CAP:
            return
        if volume_24h < MIN_VOLUME:
            return
        if fdv > MAX_MARKET_CAP:
            return
        
        # Record first call time
        if token_address not in token_call_times:
            token_call_times[token_address] = datetime.now()
        
        # Calculate minutes ago
        mins_ago = get_minutes_ago(token_address)
        
        # Get top holders (placeholder for now)
        top_10_holders = calculate_top_holders_percentage(token_address)
        
        # Format message
        message = f"""🚀 <b>{token_name}</b> ({token_symbol})

💊 <code>{token_address}</code>

📈 <a href="https://axiom.trade/t/{token_address}">Chart Watch: AXIOM</a>
💰 Market Cap: {format_number(fdv)}
🏛 Top 10 Holders: {top_10_holders}%
📊 Volume (24h): {format_number(volume_24h)}
⏰ Called: {mins_ago} min{'s' if mins_ago != 1 else ''} ago

<a href="https://dexscreener.com/solana/{token_address}">View on DexScreener</a>
"""
        
        # Send to Telegram
        result = send_telegram_message(message)
        
        if result and result.get('ok'):
            sent_tokens.add(token_address)
            print(f"✅ Posted: {token_name} ({token_symbol})")
            print(f"   MC: {format_number(fdv)} | Vol: {format_number(volume_24h)}")
        else:
            print(f"❌ Failed to post: {token_name}")
            
    except Exception as e:
        print(f"Error processing token: {e}")

def main():
    """Main bot loop"""
    print("🤖 Solana Memecoin Bot Starting...")
    print(f"📊 Filters: MC ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,} | Vol > ${MIN_VOLUME:,}")
    print(f"📱 Posting to: {TELEGRAM_CHAT_ID}")
    print("=" * 50)
    
    # Send startup message
    startup_msg = f"""🤖 <b>Memecoin Bot Online</b>

✅ Bot is now monitoring Solana tokens
📊 Active Filters:
- Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}
- Volume: > ${MIN_VOLUME:,}

🔍 Scanning every 10 seconds...
"""
    send_telegram_message(startup_msg)
    
    check_count = 0
    
    while True:
        try:
            check_count += 1
            print(f"\n🔍 Check #{check_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            # Fetch tokens
            pairs = get_solana_tokens()
            print(f"   Found {len(pairs)} pairs")
            
            # Check each pair
            for pair in pairs:
                check_and_post_token(pair)
            
            print(f"   Total posted: {len(sent_tokens)}")
            
            # Wait before next check (10 seconds for good balance)
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(30)  # Wait longer on error

if __name__ == "__main__":
    main()


