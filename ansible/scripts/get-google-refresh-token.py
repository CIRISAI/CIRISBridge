#!/usr/bin/env python3
"""
Google OAuth Refresh Token Generator for E2E Testing

One-time setup script to generate a long-lived refresh token for the
test user (ciristest1@gmail.com). The refresh token is then stored
in the Ansible vault and used for automated e2e smoke tests.

Usage:
    python3 scripts/get-google-refresh-token.py

Requirements:
    pip install google-auth google-auth-oauthlib

The script will:
1. Open a browser for Google authentication
2. Capture the authorization code
3. Exchange it for a refresh token
4. Print the refresh token for storage in vault
"""

import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Google OAuth Configuration (from CIRISBridge vault)
# These are the client IDs used for proxy token validation
CLIENT_ID = "265882853697-l421ndojcs5nm7lkln53jj29kf7kck91.apps.googleusercontent.com"
# Note: For refresh tokens, we need the client secret from Google Cloud Console
# This is a PUBLIC client (installed app), so we use a different flow

# For installed/desktop apps, Google allows using a special redirect URI
REDIRECT_URI = "http://localhost:8085"
SCOPES = ["openid", "email", "profile"]

# Token endpoint
TOKEN_URL = "https://oauth2.googleapis.com/token"

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback and capture the authorization code."""

    auth_code = None
    error = None

    def do_GET(self):
        """Handle the OAuth callback GET request."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if 'code' in params:
            OAuthCallbackHandler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        elif 'error' in params:
            OAuthCallbackHandler.error = params.get('error_description', params['error'])[0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
                <h1>Authentication Failed</h1>
                <p>Error: {OAuthCallbackHandler.error}</p>
                </body></html>
            """.encode())
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass


def get_refresh_token_with_browser():
    """
    Use browser-based OAuth flow to get a refresh token.

    Note: This uses the OAuth 2.0 for Mobile & Desktop Apps flow.
    Since we don't have the client secret for this client ID,
    we'll use PKCE (Proof Key for Code Exchange) which is
    designed for public clients.
    """
    import hashlib
    import base64
    import secrets
    import urllib.parse
    import urllib.request

    # Generate PKCE code verifier and challenge
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')

    # Build authorization URL
    auth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',  # Request refresh token
        'prompt': 'consent',  # Force consent to get refresh token
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(auth_params)}"

    print("\n" + "="*60)
    print("GOOGLE OAUTH REFRESH TOKEN GENERATOR")
    print("="*60)
    print("\n1. Opening browser for Google authentication...")
    print("   Sign in with: ciristest1@gmail.com")
    print("\n2. Grant access to the application")
    print("\n3. You'll be redirected back here automatically")
    print("\n" + "-"*60)

    # Start local server to receive callback
    server = HTTPServer(('localhost', 8085), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authentication...")
    server_thread.join(timeout=120)
    server.server_close()

    if OAuthCallbackHandler.error:
        print(f"\nError: {OAuthCallbackHandler.error}")
        sys.exit(1)

    if not OAuthCallbackHandler.auth_code:
        print("\nTimeout waiting for authentication. Please try again.")
        sys.exit(1)

    print("Authorization code received!")

    # Exchange authorization code for tokens
    print("\n4. Exchanging authorization code for tokens...")

    token_data = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'code': OAuthCallbackHandler.auth_code,
        'code_verifier': code_verifier,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=token_data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"\nError exchanging code for tokens: {error_body}")
        sys.exit(1)

    if 'refresh_token' not in tokens:
        print("\nWarning: No refresh token received!")
        print("This can happen if you've already authorized this app.")
        print("Try revoking access at: https://myaccount.google.com/permissions")
        print("\nReceived tokens:", json.dumps(tokens, indent=2))
        sys.exit(1)

    print("\n" + "="*60)
    print("SUCCESS! Refresh token generated.")
    print("="*60)
    print("\nAdd this to your Ansible vault (inventory/production.yml):\n")
    print(f'    e2e_google_refresh_token: "{tokens["refresh_token"]}"')
    print("\nThen run: ansible-vault edit inventory/production.yml")
    print("\n" + "="*60)

    # Also print the ID token for reference
    if 'id_token' in tokens:
        print("\nID Token (for testing, expires in ~1 hour):")
        print(tokens['id_token'][:50] + "...")

    return tokens['refresh_token']


def refresh_id_token(refresh_token):
    """
    Exchange a refresh token for a new ID token.
    This is what the smoke test will use.
    """
    import urllib.parse
    import urllib.request

    token_data = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=token_data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode())
            return tokens.get('id_token')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise Exception(f"Failed to refresh token: {error_body}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--refresh':
        # Test mode: exchange refresh token for ID token
        if len(sys.argv) < 3:
            print("Usage: python3 get-google-refresh-token.py --refresh <refresh_token>")
            sys.exit(1)

        refresh_token = sys.argv[2]
        id_token = refresh_id_token(refresh_token)
        print(id_token)
    else:
        # Generate new refresh token
        get_refresh_token_with_browser()
