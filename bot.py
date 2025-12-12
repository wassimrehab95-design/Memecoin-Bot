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
MIN_MARKET_CAP = 20000      # $20K
MAX_MARKET_CAP = 40000      # $40K (changed from 20M)
MIN_VOLUME = 20000          # $20K
MAX_TOKEN_AGE_MINUTES = 20  # Only tokens younger than 20 minutes

# Track sent tokens to avoid duplicates
sent_tokens = set()
token_call_times = {}

def send_telegram_message(message):
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
    try:
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
    if num is None:
        return "N/A"
    num = float(num)
    if num >= 1000000000:
        return f"${num/1000000000:.2f}B"
    elif num >= 1000000:
        return f"${num/1000000:.2f}M"
    elif num >= 1000:
        return f"${num/1000:.2f}K"
    else:
        return f"${num:.2f}"

def calculate_top_holders_percentage(token_address):
    try:
        helius_api_key = "836a3dc9-c051-4074-97a3-36098cd59efe"
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={helius_api_key}"
        return "N/A"
    except:
        return "N/A"

def get_minutes_ago(token_address):
    if token_address in token_call_times:
        time_diff = datetime.now() - token_call_times[token_address]
        return int(time_diff.total_seconds() / 60)
    return 0

def get_token_age_minutes(pair):
    """Calculate how old the token is based on pairCreatedAt"""
    try:
        pair_created = pair.get('pairCreatedAt')
        if pair_created:
            created_time = datetime.fromtimestamp(pair_created / 1000)
            age = datetime.now() - created_time
            return int(age.total_seconds() / 60)
        return None
    except:
        return None

def check_and_post_token(pair):
    try:
        token_address = pair.get('baseToken', {}).get('address')
        token_name = pair.get('baseToken', {}).get('name', 'Unknown')
        token_symbol = pair.get('baseToken', {}).get('symbol', 'Unknown')
        
        if not token_address:
            return
        
        if token_address in sent_tokens:
            return
        
        fdv = pair.get('fdv')
        volume_24h = pair.get('volume', {}).get('h24')
        liquidity = pair.get('liquidity', {}).get('usd', 0)
        
        if pair.get('chainId') != 'solana':
            return
        
        if fdv is None or volume_24h is None:
            return
            
        fdv = float(fdv)
        volume_24h = float(volume_24h)
        
        # Check market cap range: $20K - $40K
        if fdv < MIN_MARKET_CAP:
            return
        if fdv > MAX_MARKET_CAP:
            return
        
        # Check volume
        if volume_24h < MIN_VOLUME:
            return
        
        # Check token age (must be younger than 20 minutes)
        token_age = get_token_age_minutes(pair)
        if token_age is not None and token_age > MAX_TOKEN_AGE_MINUTES:
            return
        
        if token_address not in token_call_times:
            token_call_times[token_address] = datetime.now()
        
        mins_ago = get_minutes_ago(token_address)
        top_10_holders = calculate_top_holders_percentage(token_address)
        
        mins_text = "min" if mins_ago == 1 else "mins"
        age_text = f"{token_age} mins old" if token_age else "New"
        
        message = f"""🚀 <b>{token_name}</b> ({token_symbol})

💊 <code>{token_address}</code>

📈 <a href="https://axiom.trade/t/{token_address}">Chart Watch: AXIOM</a>
💰 Market Cap: {format_number(fdv)}
🏛 Top 10 Holders: {top_10_holders}%
📊 Volume (24h): {format_number(volume_24h)}
⏰ Called: {mins_ago} {mins_text} ago
🕐 Token Age: {age_text}

<a href="https://dexscreener.com/solana/{token_address}">View on DexScreener</a>
"""
        
        result = send_telegram_message(message)
        
        if result and result.get('ok'):
            sent_tokens.add(token_address)
            print(f"✅ Posted: {token_name} ({token_symbol})")
            print(f"   MC: {format_number(fdv)} | Vol: {format_number(volume_24h)} | Age: {age_text}")
        else:
            print(f"❌ Failed to post: {token_name}")
            
    except Exception as e:
        print(f"Error processing token: {e}")

def main():
    print("🤖 Solana Memecoin Bot Starting...")
    print(f"📊 Filters:")
    print(f"   • Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}")
    print(f"   • Volume: > ${MIN_VOLUME:,}")
    print(f"   • Token Age: < {MAX_TOKEN_AGE_MINUTES} minutes")
    print(f"📱 Posting to: {TELEGRAM_CHAT_ID}")
    print("=" * 50)
    
    startup_msg = f"""🤖 <b>Memecoin Bot Online</b>

✅ Bot is now monitoring Solana tokens
📊 Active Filters:
• Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}
• Volume: > ${MIN_VOLUME:,}
• Token Age: < {MAX_TOKEN_AGE_MINUTES} minutes old

🔍 Scanning every 10 seconds...
"""
    send_telegram_message(startup_msg)
    
    check_count = 0
    
    while True:
        try:
            check_count += 1
            print(f"\n🔍 Check #{check_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            pairs = get_solana_tokens()
            print(f"   Found {len(pairs)} pairs")
            
            for pair in pairs:
                check_and_post_token(pair)
            
            print(f"   Total posted: {len(sent_tokens)}")
            
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
