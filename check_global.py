import sys
sys.path.insert(0, r'c:\projects\smartfind_v3')
import ai
print(f'Module _cb_until: {ai._cb_until}')
print(f'Global dict _cb_until: {ai.__dict__.get("_cb_until", "NOT IN DICT")}')