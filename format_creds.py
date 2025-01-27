import json

# Read the credentials file
with open('credentials.json', 'r') as f:
    creds = json.load(f)

# Convert to a single line JSON string
single_line = json.dumps(creds)
print("\nCopy this entire line into Vercel GOOGLE_CREDENTIALS environment variable:")
print("=" * 80)
print(single_line)
print("=" * 80)
