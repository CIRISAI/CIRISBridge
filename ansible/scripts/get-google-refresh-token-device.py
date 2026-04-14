#!/usr/bin/env python3
"""
Google OAuth Refresh Token Generator - Device Flow
For use on remote servers without a browser.

Usage:
    python3 scripts/get-google-refresh-token-device.py
"""

import json
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# Google OAuth Device Flow Configuration
# Using the TV/Limited Input Device client type
CLIENT_ID = "265882853697-l421ndojcs5nm7lkln53jj29kf7kck91.apps.googleusercontent.com"
DEVICE_AUTH_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"


def get_device_code():
    """Request a device code from Google."""
    data = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'scope': SCOPES,
    }).encode()

    req = urllib.request.Request(DEVICE_AUTH_URL, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Error getting device code: {error_body}")
        sys.exit(1)


def poll_for_token(device_code, interval):
    """Poll for the token after user authorizes."""
    data = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
    }).encode()

    while True:
        time.sleep(interval)

        req = urllib.request.Request(TOKEN_URL, data=data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = json.loads(e.read().decode())
            error = error_body.get('error')

            if error == 'authorization_pending':
                print(".", end='', flush=True)
                continue
            elif error == 'slow_down':
                interval += 5
                continue
            elif error == 'access_denied':
                print("\n\nAccess denied by user.")
                sys.exit(1)
            elif error == 'expired_token':
                print("\n\nDevice code expired. Please try again.")
                sys.exit(1)
            else:
                print(f"\n\nError: {error_body}")
                sys.exit(1)


def main():
    print("\n" + "="*60)
    print("GOOGLE OAUTH REFRESH TOKEN GENERATOR (Device Flow)")
    print("="*60)

    # Step 1: Get device code
    print("\n1. Requesting device code...")
    device_response = get_device_code()

    user_code = device_response['user_code']
    verification_url = device_response['verification_url']
    device_code = device_response['device_code']
    interval = device_response.get('interval', 5)
    expires_in = device_response.get('expires_in', 1800)

    print("\n" + "-"*60)
    print("2. AUTHORIZATION REQUIRED")
    print("-"*60)
    print(f"\n   Go to: {verification_url}")
    print(f"\n   Enter code: {user_code}")
    print(f"\n   Sign in with: ciristest1@gmail.com")
    print(f"\n   (Code expires in {expires_in // 60} minutes)")
    print("-"*60)

    # Step 2: Poll for authorization
    print("\n3. Waiting for authorization", end='', flush=True)
    tokens = poll_for_token(device_code, interval)

    print("\n\n" + "="*60)
    print("SUCCESS! Tokens received.")
    print("="*60)

    if 'refresh_token' in tokens:
        print("\nAdd this to your Ansible vault (inventory/production.yml):\n")
        print(f'    e2e_google_refresh_token: "{tokens["refresh_token"]}"')
        print("\nRun: ansible-vault edit inventory/production.yml")
    else:
        print("\nWARNING: No refresh token received!")
        print("This can happen if the app was already authorized.")
        print("Try revoking at: https://myaccount.google.com/permissions")
        print("\nReceived:", json.dumps(tokens, indent=2))

    print("\n" + "="*60)


if __name__ == '__main__':
    main()
