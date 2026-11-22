with open(r'c:\projects\smartfind_v3\ai.py', 'r') as f:
    c = f.read()

# Replace the global declaration in ask_text (line 156) only
old = 'global _paused_until, last_error, _consecutive_failures\n'
new = 'global _paused_until, last_error, _consecutive_failures, _cb_until\n'
if old in c:
    c = c.replace(old, new, 1)  # only replace first occurrence
    with open(r'c:\projects\smartfind_v3\ai.py', 'w') as f:
        f.write(c)
    print('Done: global declaration updated')
else:
    print('Not found')