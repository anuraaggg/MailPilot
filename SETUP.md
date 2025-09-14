# MailPilot Setup Guide

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

### 4. Environment Variables
Create a `.env` file in the `backend` directory:
```env
CLIENT_ID=your_google_client_id
CLIENT_SECRET=your_google_client_secret
REDIRECT_URI=http://127.0.0.1:8000/oauth2callback
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
HUGGINGFACE_API_TOKEN=your_huggingface_token_optional
```

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
- ✅ Google OAuth authentication
- ✅ Gmail API integration
- ✅ Supabase database storage
- ✅ Email synchronization
- ✅ Beautiful dashboard UI
- ✅ Real-time unread count
- ✅ Responsive design

## Future Enhancements
- Multi-user support
- Email categorization
- Smart notifications
- Email search and filtering
- Automated sync scheduling
- Email analytics
