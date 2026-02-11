# Auth Debug Page

This page shows authentication debug information.

Access this page at: `/auth-test`

If you can see this page, authentication is working properly.

## Expected Behavior

1. First visit → Redirect to Cognito login
2. After login → Redirect to this page
3. This page loads successfully

## Troubleshooting

If you're seeing a redirect loop:
- Check that cookies are enabled in your browser
- Clear all cookies for `d2lnx09sw8wka0.cloudfront.net`
- Try in an incognito/private browsing window
