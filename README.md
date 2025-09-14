# MailPilot Setup & reCAPTCHA Guide

## Overview
MailPilot is a Gmail companion app that fetches emails from Gmail API, stores them in Supabase, and displays them in a beautiful dashboard.

## Architecture
- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: FastAPI + Python
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Google OAuth 2.0

## Setup Instructions

### 1. Supabase Setup
1. Create a new project at [supabase.com](https://supabase.com)
2. Go to Settings → API to get your project URL and anon key
3. Run the SQL schema in your Supabase SQL editor:
   ```sql
   -- Copy and paste the contents of backend/supabase_schema.sql
   ```

### 2. Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable Gmail API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://127.0.0.1:8000/oauth2callback`
5. Download the credentials JSON file

### 3. Hugging Face API Setup (Optional)
1. Go to [huggingface.co](https://huggingface.co) and create an account
2. Go to Settings → Access Tokens
3. Create a new token (optional - for higher rate limits)
4. The API works without a token but has lower rate limits

### 4. reCAPTCHA Setup

#### Get reCAPTCHA Keys
1. Go to [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin)
2. Click "Create" to create a new site
3. Choose "reCAPTCHA v2" and "I'm not a robot" checkbox
4. Add your domain (e.g., `localhost` for development)
5. Copy the **Site Key** and **Secret Key**

#### Configure Environment Variables
Add these to your `.env` file in the backend directory:
```env
CLIENT_ID=your_google_client_id
CLIENT_SECRET=your_google_client_secret
REDIRECT_URI=http://127.0.0.1:8000/oauth2callback
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
HUGGINGFACE_API_TOKEN=your_huggingface_token_optional
# reCAPTCHA Configuration
RECAPTCHA_SITE_KEY=your_site_key_here
RECAPTCHA_SECRET_KEY=your_secret_key_here
```

#### Features Implemented
- **Backend Security**: Rate limiting, user rate limiting, captcha verification, improved token refresh
- **Frontend**: Captcha modal, automatic captcha loading, better error handling, loading states

#### How It Works
1. First sync attempt: If captcha is enabled, user sees a modal with reCAPTCHA
2. Captcha verification: User completes the challenge
3. Backend validation: Server verifies the captcha response with Google
4. Rate limiting: Prevents spam by limiting requests per IP and user
5. Token refresh: Automatically refreshes expired OAuth tokens

#### Development vs Production
- **Development**: If `RECAPTCHA_SECRET_KEY` is not set, captcha verification is skipped
- **Production**: Always set both `RECAPTCHA_SITE_KEY` and `RECAPTCHA_SECRET_KEY`

#### Testing
1. Start the backend: `cd backend && python main.py`
2. Start the frontend: `cd frontend && npm run dev`
3. Login and try to sync emails
4. You should see the captcha modal (if keys are configured)

#### Troubleshooting
- Captcha not showing: Check that `RECAPTCHA_SITE_KEY` is set correctly
- Captcha verification failing: Verify `RECAPTCHA_SECRET_KEY` is correct
- Rate limit errors: Wait for the rate limit window to reset
- Token refresh errors: User may need to log in again if refresh token is invalid

### 5. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## How It Works

### Email Sync Process
1. User clicks "Sync Emails" button
2. Backend fetches last 50 emails from Gmail API
3. Emails are stored in Supabase database
4. Dashboard displays last 5 emails from database

### Authentication Flow
1. User clicks "Login with Google"
2. Redirected to Google OAuth
3. After consent, redirected back to app
4. Backend stores OAuth tokens
5. Frontend can now access dashboard

## API Endpoints
- `GET /login` - Get Google OAuth URL
- `GET /oauth2callback` - OAuth callback handler
- `GET /dashboard` - Get dashboard data from Supabase
- `POST /sync-emails` - Sync emails from Gmail to Supabase
- `GET /auth/status` - Check authentication status
- `GET /logout` - Clear stored tokens

## Database Schema
### emails table
- `id` - Primary key
- `message_id` - Gmail message ID
- `from_email` - Sender email
- `subject` - Email subject
- `date` - Email date
- `snippet` - Email preview
- `user_id` - User identifier
- `created_at` - Record creation time
- `updated_at` - Record update time

## Features
- Google OAuth authentication
- Gmail API integration
- Supabase database storage
- Email synchronization
- Beautiful dashboard UI
- Real-time unread count
- Responsive design

## Future Enhancements
- Multi-user support
- Email categorization
- Smart notifications
- Email search and filtering
- Automated sync scheduling
- Email analytics
