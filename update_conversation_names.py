#!/usr/bin/env python3
"""
Update Twilio conversation unique names
"""

import os
from twilio.rest import Client

# Get credentials from environment
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Conversations to update
conversations = [
    ('CHb7aa3110769f42a19cea7a2be9c644d2', 'league-1-warriorz'),
    ('CHc8f0c4a776f14bcd96e7c8838a6aec13', 'league-3-pal'),
    ('CHed74f2e9f16240e9a578f96299c395ce', 'league-4-party'),
    ('CH4438ff5531514178bb13c5c0e96d5579', 'league-7-bellyup'),
]

print("Updating conversation names...")
for sid, name in conversations:
    try:
        conversation = client.conversations.conversations(sid).update(
            unique_name=name
        )
        print(f"✅ Updated {sid} -> {name}")
    except Exception as e:
        print(f"❌ Error updating {sid}: {e}")

print("Done!")
