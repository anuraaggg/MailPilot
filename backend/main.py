def get_inbox_unread_count(access_token: str) -> int:
    url = "https://gmail.googleapis.com/gmail/v1/users/me/labels/INBOX"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers)
    if r.ok:
        data = r.json()
        # Exact unread message count in the Inbox
        return int(data.get("messagesUnread", 0))
    # Optional: surface error details
    raise RuntimeError(f"Gmail API error {r.status_code}: {r.text}")

# main.py
import os
import json
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import requests
from typing import Dict, Optional, List
from supabase import create_client, Client
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()  # loads CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SUPABASE_URL, SUPABASE_KEY

# Validate required environment variables
required_env_vars = ["CLIENT_ID", "CLIENT_SECRET", "REDIRECT_URI", "SUPABASE_URL", "SUPABASE_KEY"]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_label_unread(access_token, label_id):
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/labels/{label_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.ok:
        return resp.json().get("messagesUnread", 0)
    else:
        raise RuntimeError(resp.text)

def get_weekly_email_count(access_token: str) -> int:
    """Get total number of emails received this week"""
    try:
        # Calculate the date one week ago
        from datetime import datetime, timedelta
        one_week_ago = datetime.now() - timedelta(days=7)
        date_str = one_week_ago.strftime("%Y/%m/%d")
        
        # Search for emails received in the last week
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": f"after:{date_str}",
            "maxResults": 1000  # Gmail API limit
        }
        
        resp = requests.get(url, headers=headers, params=params)
        if resp.ok:
            data = resp.json()
            # Get the total count from resultSizeEstimate
            return data.get("resultSizeEstimate", 0)
        else:
            print(f"Error getting weekly email count: {resp.status_code} - {resp.text}")
            return 0
    except Exception as e:
        print(f"Exception getting weekly email count: {e}")
        return 0

def get_todays_emails(access_token: str) -> List[Dict]:
    """Get all emails received in the last 2 days with full details"""
    try:
        # Calculate today's date and yesterday for more inclusive search
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y/%m/%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        
        # Search for emails received in the last 2 days to be more inclusive
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": f"after:{yesterday}",
            "maxResults": 50  # Limit to 50 emails for summary
        }
        
        resp = requests.get(url, headers=headers, params=params)
        if not resp.ok:
            print(f"Error getting today's emails: {resp.status_code} - {resp.text}")
            return []
        
        data = resp.json()
        message_ids = [msg["id"] for msg in data.get("messages", [])]
        
        if not message_ids:
            return []
        
        # Get full details for each email
        emails = []
        for msg_id in message_ids:
            try:
                msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                msg_resp = requests.get(msg_url, headers=headers, params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
                
                if msg_resp.ok:
                    msg_data = msg_resp.json()
                    headers_map = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                    
                    from_email = headers_map.get("From", "Unknown Sender")
                    subject = headers_map.get("Subject", "No Subject")
                    date = headers_map.get("Date", "")
                    snippet = msg_data.get("snippet", "")
                    
                    # Clean up from email
                    if "<" in from_email and ">" in from_email:
                        from_email = from_email.split("<")[0].strip()
                    
                    emails.append({
                        "from_email": from_email,
                        "subject": subject,
                        "date": date,
                        "snippet": snippet,
                        "message_id": msg_id
                    })
            except Exception as e:
                print(f"Error processing email {msg_id}: {e}")
                continue
        
        print(f"Retrieved {len(emails)} emails from today")
        return emails
        
    except Exception as e:
        print(f"Exception getting today's emails: {e}")
        return []

# Hugging Face API configuration
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")  # Optional, for higher rate limits

# reCAPTCHA configuration
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

print("Hugging Face API integration ready!")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MailPilot Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# --- Health & Root endpoints ---
@app.get("/")
def root():
    return {"ok": True, "service": "MailPilot"}

@app.get("/healthz")
def healthz():
    return {"ok": True}


# CORS
origins = [
    "http://localhost:5173",
    "https://mail-pilot-eight.vercel.app"   # 👈 add your actual Vercel link here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# In-memory storage for demo purposes (use proper database in production)
user_tokens: Dict[str, Dict] = {}

def create_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("CLIENT_ID"),
                "client_secret": os.getenv("CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=os.getenv("REDIRECT_URI")
    )

def refresh_token_if_needed(credentials: Credentials) -> Optional[str]:
    """Refresh token if expired and return new access token"""
    try:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
            return credentials.token
        return credentials.token
    except Exception as e:
        print(f"Token refresh failed: {e}")
        return None

def verify_recaptcha(recaptcha_response: str, remote_ip: str) -> bool:
    """Verify reCAPTCHA response with Google"""
    if not RECAPTCHA_SECRET_KEY:
        print("Warning: RECAPTCHA_SECRET_KEY not set, skipping captcha verification")
        return True  # Skip verification in development
    
    try:
        data = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response,
            'remoteip': remote_ip
        }
        
        response = requests.post(RECAPTCHA_VERIFY_URL, data=data, timeout=10)
        result = response.json()
        
        print(f"reCAPTCHA verification result: {result}")
        return result.get('success', False)
        
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False

# Rate limiting storage (in production, use Redis)
sync_attempts = {}

def trim_old_emails(user_id: str):
    """Keep only the last MAX_EMAILS_PER_USER emails for a user"""
    try:
        # Get the cutoff email date (the N-th newest)
        result = (
            supabase.table("emails")
            .select("date")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(1)
            .range(MAX_EMAILS_PER_USER - 1, MAX_EMAILS_PER_USER - 1)
            .execute()
        )

        if not result.data:
            return  # nothing to trim

        cutoff_date = result.data[0]["date"]

        # Delete all emails older than cutoff
        (
            supabase.table("emails")
            .delete()
            .eq("user_id", user_id)
            .lt("date", cutoff_date)
            .execute()
        )

        print(f"Trimmed old emails for {user_id}, kept only {MAX_EMAILS_PER_USER}")

    except Exception as e:
        print(f"Trim error for {user_id}: {e}")


def check_sync_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded sync rate limit"""
    current_time = time.time()
    if user_id not in sync_attempts:
        sync_attempts[user_id] = []
    
    # Remove attempts older than 1 hour
    sync_attempts[user_id] = [
        attempt_time for attempt_time in sync_attempts[user_id] 
        if current_time - attempt_time < 3600
    ]
    
    # Allow max 5 sync attempts per hour
    if len(sync_attempts[user_id]) >= 5:
        return False
    
    # Record this attempt
    sync_attempts[user_id].append(current_time)
    return True

import requests
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests
from datetime import datetime
from email.utils import parsedate_to_datetime

MAX_EMAILS_PER_USER = 500   # how many emails to keep per user
TARGET_FETCH = 10           # how many emails to fetch each sync
BATCH_SIZE = 10   

def trim_old_emails(user_id: str):
    try:
        result = (
            supabase.table("emails")
            .select("message_id, date")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(MAX_EMAILS_PER_USER)
            .execute()
        )
        if not result.data:
            return

        keep_ids = [row["message_id"] for row in result.data]
        supabase.table("emails") \
            .delete() \
            .eq("user_id", user_id) \
            .not_.in_("message_id", keep_ids) \
            .execute()
        print(f"Trimmed old emails for {user_id}, kept {MAX_EMAILS_PER_USER}")
    except Exception as e:
        print(f"Trim error for {user_id}: {e}")


def sync_emails_from_gmail(access_token: str, user_id: str = "demo_user", background_tasks: BackgroundTasks = None) -> dict:
    """Fast Gmail sync: insert/update emails quickly, summaries filled later in background."""
    headers = {"Authorization": f"Bearer {access_token}"}
    base_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    try:
        # --- Step 1: List message IDs ---
        r = requests.get(
            base_url,
            headers=headers,
            params={"maxResults": TARGET_FETCH, "q": "in:inbox"},
            timeout=10
        )
        if r.status_code != 200:
            return {"error": f"Failed to fetch Gmail messages: {r.text}"}

        ids = [m["id"] for m in r.json().get("messages", [])]
        if not ids:
            return {"error": "No emails found"}

        print(f"[SYNC] Collected {len(ids)} message IDs from Gmail")

        # --- Step 2: Batch metadata fetch ---
        r = requests.post(
            f"{base_url}/batchGet",
            headers={**headers, "Content-Type": "application/json"},
            json={"ids": ids, "format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            timeout=15
        )

        messages_full = []
        if r.status_code == 200:
            messages_full = r.json().get("messages", []) or []
            print(f"[SYNC] BatchGet returned {len(messages_full)} messages")

            # Fallback for missing messages
            if len(messages_full) < len(ids):
                missing_ids = list(set(ids) - {m.get("id") for m in messages_full})
                print(f"[SYNC] BatchGet missed {len(missing_ids)} messages, fetching individually...")
                for mid in missing_ids:
                    try:
                        r_one = requests.get(
                            f"{base_url}/{mid}",
                            headers=headers,
                            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                            timeout=10
                        )
                        if r_one.status_code == 200:
                            messages_full.append(r_one.json())
                        else:
                            print(f"[SYNC] Individual fetch failed for {mid}: {r_one.status_code}")
                    except Exception as e:
                        print(f"[SYNC] Error fetching {mid}: {e}")
        else:
            print(f"[SYNC] Batch fetch failed with {r.status_code}, falling back to individual requests")
            for i, mid in enumerate(ids):
                if i % 10 == 0:
                    print(f"[SYNC] Fallback progress: {i}/{len(ids)}")
                try:
                    r_one = requests.get(
                        f"{base_url}/{mid}",
                        headers=headers,
                        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                        timeout=10
                    )
                    if r_one.status_code == 200:
                        messages_full.append(r_one.json())
                except Exception as e:
                    print(f"[SYNC] Error fetching {mid}: {e}")

        print(f"[SYNC] Retrieved {len(messages_full)} messages from Gmail")

        if not messages_full:
            return {"error": "No messages retrieved from Gmail API"}

        # Debug: Print first few email subjects to see what we're getting
        print(f"[SYNC] Sample of fetched emails:")
        for i, msg in enumerate(messages_full[:5]):
            headers_map = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers_map.get("Subject", "No Subject")
            from_email = headers_map.get("From", "Unknown Sender")
            print(f"  {i+1}. {from_email} | {subject}")
        

        # --- Step 3: Normalize ---
        emails_to_store = []
        for msg in messages_full:
            msg_id = msg["id"]
            headers_map = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            from_email = headers_map.get("From", "Unknown Sender")
            subject = headers_map.get("Subject", "No Subject")
            snippet = msg.get("snippet", "")
            internal_ts = int(msg.get("internalDate", 0)) / 1000
            parsed_date = datetime.fromtimestamp(internal_ts, tz=timezone.utc)

            if "<" in from_email and ">" in from_email:
                from_email = from_email.split("<")[0].strip()

            emails_to_store.append({
                "message_id": msg_id,
                "from_email": from_email,
                "subject": subject,
                "date": parsed_date.isoformat(),
                "snippet": snippet,
                "summary": None,  # fill later
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        print(f"[SYNC] Normalized {len(emails_to_store)} messages")

        # --- Step 4: Insert into Supabase (with manual dedup) ---
        if emails_to_store:
            # First, get existing message IDs to avoid duplicates
            existing_ids = set()
            try:
                existing_result = supabase.table("emails").select("message_id, subject").eq("user_id", user_id).execute()
                if existing_result.data:
                    existing_ids = {row["message_id"] for row in existing_result.data}
                    print(f"[SYNC] Found {len(existing_ids)} existing emails in database")
                    # Debug: Show some existing email subjects
                    print(f"[SYNC] Sample existing emails:")
                    for row in existing_result.data[:3]:
                        print(f"  - {row['subject'][:50]}... | ID: {row['message_id']}")
                else:
                    print(f"[SYNC] No existing emails in database")
            except Exception as e:
                print(f"[SYNC] Warning: Could not check existing emails: {e}")
            
            # Filter out emails that already exist
            new_emails = [email for email in emails_to_store if email["message_id"] not in existing_ids]
            print(f"[SYNC] {len(new_emails)} new emails to insert (filtered from {len(emails_to_store)})")
            
            # Debug: Show which emails are being filtered out
            if len(new_emails) < len(emails_to_store):
                filtered_out = [email for email in emails_to_store if email["message_id"] in existing_ids]
                print(f"[SYNC] Filtered out {len(filtered_out)} existing emails:")
                for email in filtered_out[:5]:  # Show first 5
                    print(f"  - {email['from_email']} | {email['subject'][:50]}... | ID: {email['message_id']}")
            
            # Debug: Show which emails are new
            if new_emails:
                print(f"[SYNC] New emails to insert:")
                for email in new_emails[:5]:  # Show first 5
                    print(f"  + {email['from_email']} | {email['subject'][:50]}... | ID: {email['message_id']}")
            
            
            if new_emails:
                # Insert new emails in batches
                batch_size = 10
                for i in range(0, len(new_emails), batch_size):
                    batch = new_emails[i:i + batch_size]
                    try:
                        supabase.table("emails").insert(batch).execute()
                        print(f"[SYNC] Inserted batch {i//batch_size + 1}: {len(batch)} emails")
                    except Exception as e:
                        print(f"[SYNC] Error inserting batch {i//batch_size + 1}: {e}")
                        # Try inserting one by one if batch fails
                        for email in batch:
                            try:
                                supabase.table("emails").insert([email]).execute()
                                print(f"[SYNC] Inserted individual email: {email['subject'][:30]}...")
                            except Exception as e2:
                                print(f"[SYNC] Failed to insert individual email: {e2}")
            else:
                print(f"[SYNC] No new emails to insert")

        # --- Step 5: Background summaries ---
        if background_tasks and emails_to_store:
            background_tasks.add_task(
                generate_summaries_in_background,
                user_id,
                [row["message_id"] for row in emails_to_store]
            )

        # --- Step 6: Trim old emails ---
        trim_old_emails(user_id)

        return {
            "success": True,
            "emails_synced": len(emails_to_store),
            "gmail_ids_seen": len(ids),
        }

    except Exception as e:
        print(f"[SYNC] Fatal error: {e}")
        return {"error": f"Sync failed: {str(e)}"}


def generate_summaries_in_background(user_id: str, message_ids: list):
    """Slow background task: generate summaries and update Supabase."""
    print(f"[BG] Summarizing {len(message_ids)} emails for {user_id}...")
    for mid in message_ids:
        try:
            resp = supabase.table("emails").select("*").eq("user_id", user_id).eq("message_id", mid).single().execute()
            if not resp.data:
                continue

            email = resp.data
            summary = generate_email_summary(email["subject"], email["snippet"])

            supabase.table("emails").update({"summary": summary}).eq("message_id", mid).execute()
            print(f"[BG] Done: {email['subject'][:40]}...")
        except Exception as e:
            print(f"[BG] Error summarizing {mid}: {e}")


def get_emails_from_supabase(user_id: str = "demo_user", limit: int = 5) -> List[Dict]:
    """Get emails from Supabase database"""
    try:
        # Get emails ordered by date (actual email date) descending to show newest first
        result = supabase.table("emails").select("*").eq("user_id", user_id).order("date", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Supabase query error: {e}")
        # Fallback to created_at ordering if date ordering fails
        try:
            result = supabase.table("emails").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e2:
            print(f"Fallback query error: {e2}")
        return []

def get_user_keywords(user_id: str = "demo_user") -> List[str]:
    """Get user's keywords from Supabase"""
    try:
        result = supabase.table("keywords").select("keyword").eq("user_id", user_id).execute()
        return [row["keyword"] for row in result.data] if result.data else []
    except Exception as e:
        print(f"Keywords query error: {e}")
        return []

def add_user_keyword(user_id: str, keyword: str) -> Dict:
    """Add a keyword for a user"""
    try:
        # Check if keyword already exists
        existing = supabase.table("keywords").select("*").eq("user_id", user_id).eq("keyword", keyword.lower().strip()).execute()
        
        if existing.data:
            return {"error": "Keyword already exists"}
        
        # Insert new keyword
        result = supabase.table("keywords").insert({
            "user_id": user_id,
            "keyword": keyword.lower().strip()
        }).execute()
        
        return {"success": True, "message": f"Keyword '{keyword}' added successfully"}
    except Exception as e:
        print(f"Add keyword error: {e}")
        return {"error": f"Failed to add keyword: {str(e)}"}

def remove_user_keyword(user_id: str, keyword: str) -> Dict:
    """Remove a keyword for a user"""
    try:
        result = supabase.table("keywords").delete().eq("user_id", user_id).eq("keyword", keyword.lower().strip()).execute()
        return {"success": True, "message": f"Keyword '{keyword}' removed successfully"}
    except Exception as e:
        print(f"Remove keyword error: {e}")
        return {"error": f"Failed to remove keyword: {str(e)}"}

def get_important_emails(user_id: str = "demo_user", limit: int = 3) -> List[Dict]:
    """Get emails that contain user's keywords"""
    try:
        keywords = get_user_keywords(user_id)
        print(f"User keywords: {keywords}")
        
        if not keywords:
            print("No keywords found for user")
            return []
        
        # Get all emails for the user ordered by date (newest first)
        try:
            all_emails = supabase.table("emails").select("*").eq("user_id", user_id).order("date", desc=True).execute()
        except Exception as e:
            print(f"Date ordering failed, trying created_at: {e}")
            all_emails = supabase.table("emails").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        if not all_emails.data:
            print("No emails found in database")
            return []
        
        print(f"Checking {len(all_emails.data)} emails against keywords")
        
        # Filter emails that contain any of the keywords
        important_emails = []
        for email in all_emails.data:
            subject = email.get("subject", "").lower()
            snippet = email.get("snippet", "").lower()
            from_email = email.get("from_email", "").lower()
            
            # Check if any keyword is in subject, snippet, or from email
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if (keyword_lower in subject or 
                    keyword_lower in snippet or 
                    keyword_lower in from_email):
                    print(f"Found match: '{keyword}' in email '{subject[:30]}...'")
                    important_emails.append(email)
                    break
        
        print(f"Found {len(important_emails)} important emails")
        # Return the most recent important emails
        return important_emails[:limit]
    except Exception as e:
        print(f"Important emails query error: {e}")
        return []

def generate_email_summary(subject: str, snippet: str) -> str:
    """Generate a summary of the email using Hugging Face API"""
    try:
        # Combine subject and snippet for better context
        text_to_summarize = f"Subject: {subject}\n\n{snippet}"
        
        # Truncate if too long (API has token limits)
        if len(text_to_summarize) > 1000:
            text_to_summarize = text_to_summarize[:1000]
        
        # Prepare API request
        headers = {"Content-Type": "application/json"}
        if HUGGINGFACE_API_TOKEN:
            headers["Authorization"] = f"Bearer {HUGGINGFACE_API_TOKEN}"
        
        payload = {
            "inputs": text_to_summarize,
            "parameters": {
                "max_length": 80,
                "min_length": 15,
                "do_sample": False
            }
        }
        
        # Make API request
        response = requests.post(HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                summary = result[0]['summary_text']
                return summary
            else:
                print(f"Unexpected API response format: {result}")
                return snippet[:100] + "..." if len(snippet) > 100 else snippet
        else:
            print(f"Hugging Face API error: {response.status_code} - {response.text}")
            return snippet[:100] + "..." if len(snippet) > 100 else snippet
            
    except requests.exceptions.Timeout:
        print("Hugging Face API timeout")
        return snippet[:100] + "..." if len(snippet) > 100 else snippet
    except Exception as e:
        print(f"Summarization error: {e}")
        # Fallback to snippet if summarization fails
        return snippet[:100] + "..." if len(snippet) > 100 else snippet

def generate_daily_summary(todays_emails: List[Dict], weekly_count: int, keywords: List[str]) -> str:
    """Generate a comprehensive daily summary using today's emails and keywords"""
    try:
        print(f"DEBUG: generate_daily_summary called with {len(todays_emails)} emails, {len(keywords)} keywords")
        print(f"DEBUG: Keywords: {keywords}")
        
        if not todays_emails:
            print("DEBUG: No today's emails, returning basic summary")
            return f"You received {weekly_count} emails this week. No emails received today."
        
        # Categorize emails by keywords
        important_emails = []
        general_emails = []
        keyword_matches = {}
        
        print(f"DEBUG: Processing {len(todays_emails)} emails for keyword matching")
        
        for i, email in enumerate(todays_emails):
            subject = email.get("subject", "").lower()
            snippet = email.get("snippet", "").lower()
            from_email = email.get("from_email", "").lower()
            
            print(f"DEBUG: Processing email {i+1}: Subject='{subject[:50]}...', From='{from_email[:30]}...'")
            
            # Check which keywords this email matches
            matched_keywords = []
            for keyword in keywords:
                keyword_lower = keyword.lower().strip()
                # More flexible matching - check for partial matches and variations
                if (keyword_lower in subject or 
                    keyword_lower in snippet or 
                    keyword_lower in from_email or
                    any(word in subject for word in keyword_lower.split()) or
                    any(word in snippet for word in keyword_lower.split())):
                    matched_keywords.append(keyword)
                    if keyword not in keyword_matches:
                        keyword_matches[keyword] = []
                    keyword_matches[keyword].append(email)
                    print(f"DEBUG: Email matched keyword '{keyword}': Subject='{subject[:50]}...', Snippet='{snippet[:50]}...'")
            
            if matched_keywords:
                important_emails.append(email)
            else:
                general_emails.append(email)
        
        print(f"DEBUG: Keyword matching results - Important: {len(important_emails)}, General: {len(general_emails)}")
        print(f"DEBUG: Keyword matches: {keyword_matches}")
        
        # Build comprehensive paragraph-style summary
        summary_parts = []
        
        # Start with email count and time context
        from datetime import datetime
        current_time = datetime.now().strftime("%A, %B %d")
        summary_parts.append(f"On {current_time}, you received {len(todays_emails)} emails")
        
        # Keyword-specific insights
        if keyword_matches:
            keyword_details = []
            for keyword, emails in keyword_matches.items():
                if len(emails) > 0:
                    # Get unique senders for this keyword
                    senders = set()
                    subjects = []
                    for email in emails[:4]:  # Show up to 4 emails for more detail
                        from_email = email.get("from_email", "Unknown Sender")
                        if "<" in from_email and ">" in from_email:
                            from_email = from_email.split("<")[0].strip()
                        senders.add(from_email)
                        subjects.append(email.get("subject", "No Subject")[:100])  # Longer subject lines
                    
                    sender_list = list(senders)[:3]  # Show up to 3 senders
                    if len(sender_list) == 1:
                        sender_text = f"from {sender_list[0]}"
                    elif len(sender_list) == 2:
                        sender_text = f"from {sender_list[0]} and {sender_list[1]}"
                    else:
                        sender_text = f"from {sender_list[0]}, {sender_list[1]}, and {sender_list[2]}"
                    
                    # Add keyword details with complete subject lines
                    if len(emails) == 1:
                        keyword_details.append(f"1 email matching '{keyword}' {sender_text}: \"{subjects[0]}\"")
                    else:
                        keyword_details.append(f"{len(emails)} emails matching '{keyword}' {sender_text}")
                        keyword_details.append(f"including \"{subjects[0]}\"")
                        if len(subjects) > 1:
                            keyword_details.append(f"\"{subjects[1]}\"")
                        if len(subjects) > 2:
                            keyword_details.append(f"\"{subjects[2]}\"")
                        if len(emails) > 3:
                            keyword_details.append(f"and {len(emails)-3} more")
            
            if keyword_details:
                summary_parts.append(f"Found {', '.join(keyword_details)}")
        
        # General email insights with more detail
        if general_emails:
            # Get top senders from general emails
            senders = {}
            for email in general_emails:
                from_email = email.get("from_email", "Unknown Sender")
                if "<" in from_email and ">" in from_email:
                    from_email = from_email.split("<")[0].strip()
                senders[from_email] = senders.get(from_email, 0) + 1
            
            # Sort by frequency and take top 6 for more detail
            top_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:6]
            
            if top_senders:
                sender_text = []
                for sender, count in top_senders:
                    if count == 1:
                        sender_text.append(sender)
                    else:
                        sender_text.append(f"{sender} ({count} emails)")
                
                if len(sender_text) == 1:
                    summary_parts.append(f"Other emails came from {sender_text[0]}")
                elif len(sender_text) <= 4:
                    summary_parts.append(f"Other emails came from {', '.join(sender_text)}")
                else:
                    summary_parts.append(f"Other emails came from {', '.join(sender_text[:4])} and {len(sender_text)-4} others")
        
        # Weekly context with more detail
        if weekly_count > len(todays_emails):
            remaining_week = weekly_count - len(todays_emails)
            summary_parts.append(f"bringing your weekly total to {weekly_count} emails ({remaining_week} from previous days)")
        else:
            summary_parts.append(f"bringing your weekly total to {weekly_count} emails")
        
        return ". ".join(summary_parts) + "."
        
    except Exception as e:
        print(f"Daily summary generation error: {e}")
        return f"You received {len(todays_emails) if todays_emails else 0} emails today. {weekly_count} total this week."


@app.get("/login")
def login():
    flow = create_flow()
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    # 🔍 Debug prints
    print(f"DEBUG Redirect URI in use: {os.getenv('REDIRECT_URI')!r}")
    print(f"DEBUG Generated auth_url: {auth_url}")

    return {"auth_url": auth_url}



@app.get("/oauth2callback")
def oauth2callback(request: Request, code: str):
    if not code:
        return JSONResponse({"error": "Authorization code not provided"}, status_code=400)
    
    flow = create_flow()
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        print(f"OAuth error: {e}")
        return JSONResponse({"error": "Failed to exchange authorization code for tokens"}, status_code=400)

    credentials = flow.credentials
    
    # Store credentials for the user (in production, use proper user identification)
    user_id = "demo_user"  # In production, get from session or JWT
    user_tokens[user_id] = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expiry.timestamp() if credentials.expiry else None,
        "scopes": credentials.scopes
    }

    print(f"OAuth successful! Stored token for user: {user_id}")
    print(f"Token data: {user_tokens[user_id]}")
    
    # Verify token storage before redirecting
    if user_id in user_tokens and user_tokens[user_id].get("access_token"):
        print("Token storage verified successfully")
        
        # Trigger automatic sync after successful login
        try:
            print("Starting automatic email sync after login...")
            # Create a dummy background tasks for auto-sync
            from fastapi import BackgroundTasks
            dummy_background_tasks = BackgroundTasks()
            sync_result = sync_emails_from_gmail(credentials.token, user_id, dummy_background_tasks)
            print(f"Auto-sync result: {sync_result}")
        except Exception as e:
            print(f"Auto-sync failed (non-critical): {e}")
            # Don't fail the login if sync fails
    else:
        print("ERROR: Token storage failed!")
        return JSONResponse({"error": "Failed to store authentication tokens"}, status_code=500)

    # Redirect to frontend with success indicator
    # Try different possible frontend URLs
    frontend_urls = [
        "http://localhost:5173/dashboard?auth_success=true",
        "http://127.0.0.1:5173/dashboard?auth_success=true",
        "http://localhost:3000/dashboard?auth_success=true",
        "http://127.0.0.1:3000/dashboard?auth_success=true"
    ]
    
    # Use the first URL for now, but we can make this configurable
    redirect_url = frontend_urls[0]
    print(f"Redirecting to: {redirect_url}")
    return RedirectResponse(redirect_url)


@app.get("/dashboard")
def get_dashboard(request: Request):
    # For demo purposes, get the stored token
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    try:
        # Get emails from Supabase database
        emails = get_emails_from_supabase(user_id, limit=5)
        print(f"Retrieved {len(emails)} emails from Supabase for dashboard")
        
        # If no emails in database, trigger a sync
        if not emails:
            print("No emails found in database, triggering automatic sync...")
            try:
                token_data = user_tokens[user_id]
                credentials = Credentials(
                    token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.getenv("CLIENT_ID"),
                    client_secret=os.getenv("CLIENT_SECRET"),
                    scopes=token_data["scopes"]
                )
                
                access_token = refresh_token_if_needed(credentials)
                if access_token:
                    # Create a dummy background tasks for auto-sync
                    from fastapi import BackgroundTasks
                    dummy_background_tasks = BackgroundTasks()
                    sync_result = sync_emails_from_gmail(access_token, user_id, dummy_background_tasks)
                    print(f"Auto-sync result: {sync_result}")
                    
                    # Re-fetch emails after sync
                    emails = get_emails_from_supabase(user_id, limit=5)
                    print(f"After sync, retrieved {len(emails)} emails from Supabase")
            except Exception as e:
                print(f"Auto-sync failed: {e}")
                # Continue with empty emails list
        
        # Get weekly email count from Gmail API
        token_data = user_tokens[user_id]
        credentials = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET"),
            scopes=token_data["scopes"]
        )

        access_token = refresh_token_if_needed(credentials)
        weekly_email_count = 0
        todays_emails = []
        if access_token:
            try:
                weekly_email_count = get_weekly_email_count(access_token)
                print(f"Weekly email count: {weekly_email_count}")
                
                # Get today's emails for better summary
                todays_emails = get_todays_emails(access_token)
                print(f"Today's emails: {len(todays_emails)}")
            except Exception as e:
                print(f"Error getting email data: {e}")

        # Get important emails based on user keywords
        important_emails = get_important_emails(user_id, limit=3)
        user_keywords = get_user_keywords(user_id)
        
        # Format emails for frontend
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                "from": email.get("from_email", "Unknown Sender"),
                "subject": email.get("subject", "No Subject"),
                "date": email.get("date", "Unknown Date")[:10] if email.get("date") else "Unknown Date",
                "summary": email.get("summary", email.get("snippet", ""))
            })
        
        # Format important emails for frontend
        formatted_important_emails = []
        for email in important_emails:
            formatted_important_emails.append({
                "from": email.get("from_email", "Unknown Sender"),
                "subject": email.get("subject", "No Subject"),
                "date": email.get("date", "Unknown Date")[:10] if email.get("date") else "Unknown Date",
                "summary": email.get("summary", email.get("snippet", ""))
            })

        # Generate comprehensive daily summary using today's emails and keywords
        total_emails_in_db = len(emails)
        important_count = len(formatted_important_emails)
        
        if total_emails_in_db == 0 and not todays_emails:
            daily_summary = f"You received {weekly_email_count} emails this week. Sync your emails to see them here."
        else:
            # Generate summary using today's emails and keywords
            print(f"DEBUG: Generating summary with {len(todays_emails)} today's emails and {len(user_keywords)} keywords")
            print(f"DEBUG: Keywords: {user_keywords}")
            print(f"DEBUG: Today's emails sample: {todays_emails[:2] if todays_emails else 'None'}")
            daily_summary = generate_daily_summary(todays_emails, weekly_email_count, user_keywords)
            print(f"DEBUG: Generated summary: {daily_summary}")

        return {
            "unreadEmails": weekly_email_count,
            "importantEmails": formatted_important_emails,
            "keywords": user_keywords,
            "dailySummary": daily_summary,
            "activeUsers": 1,
            "activeAccounts": 1,
            "recentEmails": formatted_emails
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/sync-emails")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
def sync_emails(request: Request, background_tasks: BackgroundTasks, captcha_data: dict = None):
    """Sync emails from Gmail API to Supabase database with captcha verification"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Check rate limit
    if not check_sync_rate_limit(user_id):
        raise HTTPException(
            status_code=429, 
            detail="Too many sync attempts. Please wait before trying again."
        )
    
    # Verify captcha if provided
    if captcha_data and captcha_data.get("captcha_response"):
        captcha_response = captcha_data["captcha_response"]
        
        # Allow "skipped" for development/testing
        if captcha_response == "skipped":
            print("Captcha verification skipped for development")
        else:
            client_ip = get_remote_address(request)
            if not verify_recaptcha(captcha_response, client_ip):
                raise HTTPException(status_code=400, detail="Invalid captcha verification")
    elif RECAPTCHA_SECRET_KEY:
        # If captcha is configured but not provided, require it
        raise HTTPException(status_code=400, detail="Captcha verification required")
    
    token_data = user_tokens[user_id]
    credentials = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scopes=token_data["scopes"]
    )
    
    access_token = refresh_token_if_needed(credentials)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed. Please log in again.")
    
    # Sync emails from Gmail to Supabase
    result = sync_emails_from_gmail(access_token, user_id, background_tasks)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@app.get("/debug/emails")
def debug_emails():
    """Debug endpoint to check Gmail API response"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    token_data = user_tokens[user_id]
    credentials = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scopes=token_data["scopes"]
    )
    
    access_token = refresh_token_if_needed(credentials)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    try:
        # Fetch messages
        print(f"Debug: Testing Gmail API with token: {access_token[:20]}...")
        messages_resp = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        print(f"Debug: Gmail API response status: {messages_resp.status_code}")
        print(f"Debug: Gmail API response: {messages_resp.text[:500]}...")
        
        if messages_resp.status_code != 200:
            return {
                "error": f"Failed to fetch messages: {messages_resp.status_code}", 
                "response": messages_resp.text,
                "status_code": messages_resp.status_code,
                "headers": dict(messages_resp.headers)
            }
        
        messages_data = messages_resp.json()
        
        # Get first message details
        if "messages" in messages_data and len(messages_data["messages"]) > 0:
            msg_id = messages_data["messages"][0]["id"]
            print(f"Debug: Fetching details for message {msg_id}")
            msg_resp = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            print(f"Debug: Message details response status: {msg_resp.status_code}")
            
            return {
                "messages_list": messages_data,
                "first_message": msg_resp.json() if msg_resp.status_code == 200 else {"error": f"Failed to fetch message: {msg_resp.status_code}", "response": msg_resp.text},
                "access_token_preview": access_token[:20] + "...",
                "total_messages": len(messages_data.get("messages", []))
            }
        else:
            return {"error": "No messages found", "messages_list": messages_data}
            
    except Exception as e:
        print(f"Debug error: {e}")
        return {"error": str(e), "traceback": str(e.__traceback__)}

@app.get("/keywords")
def get_keywords():
    """Get user's keywords"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    keywords = get_user_keywords(user_id)
    return {"keywords": keywords}

@app.post("/keywords")
def add_keyword(keyword_data: dict):
    """Add a keyword for the user"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    keyword = keyword_data.get("keyword", "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")
    
    result = add_user_keyword(user_id, keyword)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@app.delete("/keywords/{keyword}")
def remove_keyword(keyword: str):
    """Remove a keyword for the user"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    result = remove_user_keyword(user_id, keyword)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@app.get("/auth/status")
def auth_status():
    """Check authentication status"""
    user_id = "demo_user"
    if user_id in user_tokens:
        return {
            "authenticated": True,
            "user_id": user_id,
            "has_access_token": "access_token" in user_tokens[user_id],
            "has_refresh_token": "refresh_token" in user_tokens[user_id]
        }
    else:
        return {"authenticated": False, "user_id": user_id}

@app.get("/logout")
def logout():
    """Clear stored tokens"""
    user_id = "demo_user"
    if user_id in user_tokens:
        del user_tokens[user_id]
    return {"message": "Logged out successfully"}

@app.get("/captcha/config")
def get_captcha_config():
    """Get reCAPTCHA site key for frontend"""
    return {
        "site_key": os.getenv("RECAPTCHA_SITE_KEY"),
        "enabled": bool(RECAPTCHA_SECRET_KEY)
    }
@app.get("/debug/primary-sample")
def debug_primary_sample():
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")

    token_data = user_tokens[user_id]
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scopes=token_data["scopes"],
    )
    access_token = refresh_token_if_needed(creds)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params={"maxResults": 10, "q": "in:inbox"}
    )
    if r.status_code != 200:
        return {"error": r.text}
    ids = [m["id"] for m in r.json().get("messages", [])]
    if not ids:
        return {"ids": []}

    r2 = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchGet",
        headers={**headers, "Content-Type": "application/json"},
        json={"ids": ids, "format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
    )
    sample = []
    for m in r2.json().get("messages", []):
        h = {hh["name"]: hh["value"] for hh in m.get("payload", {}).get("headers", [])}
        sample.append({"id": m.get("id"), "from": h.get("From"), "subject": h.get("Subject"), "date": h.get("Date")})
    return {"sample": sample}

@app.get("/debug/search-secret-email")
def debug_search_secret_email():
    """Debug endpoint to specifically search for the 'secret to adulthood' email"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")

    token_data = user_tokens[user_id]
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scopes=token_data["scopes"],
    )
    access_token = refresh_token_if_needed(creds)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Search for emails with "secret" and "adulthood" in subject
    search_queries = [
        "in:inbox subject:secret subject:adulthood",
        "in:inbox secret adulthood",
        "in:inbox from:gemini",
        "in:inbox subject:stress"
    ]
    
    results = {}
    for query in search_queries:
        try:
            r = requests.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"maxResults": 10, "q": query}
            )
            if r.status_code == 200:
                messages = r.json().get("messages", [])
                results[query] = {
                    "count": len(messages),
                    "message_ids": [m["id"] for m in messages]
                }
            else:
                results[query] = {"error": f"Status {r.status_code}: {r.text}"}
        except Exception as e:
            results[query] = {"error": str(e)}
    
    return {"search_results": results}

@app.post("/debug/force-sync")
def debug_force_sync():
    """Debug endpoint to force a fresh sync without rate limiting"""
    user_id = "demo_user"
    if user_id not in user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    token_data = user_tokens[user_id]
    credentials = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        scopes=token_data["scopes"]
    )
    
    access_token = refresh_token_if_needed(credentials)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed. Please log in again.")
    
    # Force sync emails from Gmail to Supabase
    from fastapi import BackgroundTasks
    dummy_background_tasks = BackgroundTasks()
    result = sync_emails_from_gmail(access_token, user_id, dummy_background_tasks)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result
