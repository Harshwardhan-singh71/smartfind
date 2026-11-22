with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    c = f.read()

# Remove all [DBG2] debug prints
c = c.replace('print(f"[DBG2] busy={busy} msg={message} _consec={_consecutive_failures}")', '')

# Change ai._cb_until to _cb_until (first occurrence in ask_text)
c = c.replace('ai._cb_until = time.time() + BREAKER_PAUSE', '_cb_until = time.time() + BREAKER_PAUSE', 1)

with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
    f.write(c)
print('Done')