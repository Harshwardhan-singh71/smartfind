import sys

with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    content = f.read()

# Add debug print after busy line
old = 'busy = ("503" in message or "504" in message or "unavailable" in message\n                    or "deadline" in message or "timed out" in message or "timeout" in message)\n            if busy:'
new = 'busy = ("503" in message or "504" in message or "unavailable" in message\n                    or "deadline" in message or "timed out" in message or "timeout" in message)\n            print(f"[DBG2] busy={busy} msg={message} _consec={_consecutive_failures}")\n            if busy:'

if old in content:
    content = content.replace(old, new)
    with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
        f.write(content)
    print('Replacement done')
else:
    print('Pattern not found')
    # Show what we have around busy
    idx = content.find('busy =')
    if idx >= 0:
        print(content[idx:idx+200])