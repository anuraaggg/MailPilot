# reCAPTCHA Setup Guide

This guide will help you set up Google reCAPTCHA v2 for the MailPilot sync functionality.

## 1. Get reCAPTCHA Keys

1. Go to [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin)
2. Click "Create" to create a new site
3. Choose "reCAPTCHA v2" and "I'm not a robot" checkbox
4. Add your domain (e.g., `localhost` for development)
5. Copy the **Site Key** and **Secret Key**

## 2. Configure Environment Variables

Add these to your `.env` file in the backend directory:

```env
# reCAPTCHA Configuration
RECAPTCHA_SITE_KEY=your_site_key_here
RECAPTCHA_SECRET_KEY=your_secret_key_here
```

## 3. Features Implemented

### Backend Security Features:
- **Rate Limiting**: Maximum 10 sync requests per minute per IP
- **User Rate Limiting**: Maximum 5 sync attempts per hour per user
- **Captcha Verification**: Validates reCAPTCHA response with Google's API
- **Improved Token Refresh**: Better error handling for expired tokens

### Frontend Features:
- **Captcha Modal**: Shows when sync is attempted (if captcha is enabled)
- **Automatic Captcha Loading**: Loads reCAPTCHA widget dynamically
- **Better Error Handling**: Shows specific error messages for rate limits and captcha failures
- **Loading States**: Visual feedback during sync operations

## 4. How It Works

1. **First Sync Attempt**: If captcha is enabled, user sees a modal with reCAPTCHA
2. **Captcha Verification**: User completes the "I'm not a robot" challenge
3. **Backend Validation**: Server verifies the captcha response with Google
4. **Rate Limiting**: Prevents spam by limiting requests per IP and user
5. **Token Refresh**: Automatically refreshes expired OAuth tokens without requiring re-login

## 5. Development vs Production

- **Development**: If `RECAPTCHA_SECRET_KEY` is not set, captcha verification is skipped
- **Production**: Always set both `RECAPTCHA_SITE_KEY` and `RECAPTCHA_SECRET_KEY`

## 6. Testing

1. Start the backend: `cd backend && python main.py`
2. Start the frontend: `cd frontend && npm run dev`
3. Login and try to sync emails
4. You should see the captcha modal (if keys are configured)

## 7. Troubleshooting

- **Captcha not showing**: Check that `RECAPTCHA_SITE_KEY` is set correctly
- **Captcha verification failing**: Verify `RECAPTCHA_SECRET_KEY` is correct
- **Rate limit errors**: Wait for the rate limit window to reset (1 hour for user limits)
- **Token refresh errors**: User may need to log in again if refresh token is invalid
