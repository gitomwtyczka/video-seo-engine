#!/usr/bin/env python3
"""Patch nginx config: add /v1/ location block for VSE Local Runner."""
import sys

CONF = '/home/ubuntu/crimson-void/nginx/default.conf'

V1_BLOCK = """
    # FastAPI direct: /v1/* -> 8085 (Local Runner + all FastAPI endpoints)
    location /v1/ {
        proxy_pass http://172.17.0.1:8085/v1/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s; proxy_connect_timeout 10s; proxy_send_timeout 300s;
    }
"""

with open(CONF) as f:
    content = f.read()

if 'location /v1/' in content:
    print('OK: /v1/ block already present')
    sys.exit(0)

LINE_AFTER = '    location /health { proxy_pass http://172.17.0.1:8085/health; proxy_set_header Host $host; }'

if LINE_AFTER not in content:
    print('ERROR: anchor line not found. Config may have changed.')
    sys.exit(1)

content = content.replace(LINE_AFTER, LINE_AFTER + V1_BLOCK)

with open(CONF, 'w') as f:
    f.write(content)

print('OK: /v1/ block inserted successfully')
