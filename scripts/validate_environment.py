#!/usr/bin/env python3
"""Check deployment settings without printing their secret values."""
import argparse,sys
from pathlib import Path
from urllib.parse import urlsplit
p=argparse.ArgumentParser();p.add_argument('--env-file',required=True);a=p.parse_args();env={}
for line in Path(a.env_file).read_text().splitlines():
 if line.strip() and not line.lstrip().startswith('#') and '=' in line:
  key,value=line.split('=',1);env[key.strip()]=value.strip().strip('\"\'')
errors=[]
for key in ['JWT_SECRET','SESSION_SECRET','POSTGRES_PASSWORD','APP_DB_PASSWORD','MIGRATION_DB_PASSWORD','KEYCLOAK_DB_PASSWORD','MLFLOW_DB_PASSWORD','KEYCLOAK_ADMIN_PASSWORD','AUDIT_HMAC_KEY']:
 value=env.get(key,'')
 if len(value)<32 or any(x in value.lower() for x in ['change_me','change-me','replace','password']):errors.append(key+': strong secret required')
for key in ['APP_PUBLIC_URL','KEYCLOAK_PUBLIC_URL']:
 if urlsplit(env.get(key,'')).scheme!='https':errors.append(key+': HTTPS URL required')
for key in ['ALLOW_DEV_AUTH','ALLOW_DEV_RBAC','ALLOW_EXTERNAL_AI','ALLOW_EXTERNAL_APIS']:
 if env.get(key,'false').lower()!='false':errors.append(key+': must be false')
if env.get('HSAAI_APP_ENV')!='production':errors.append('HSAAI_APP_ENV must be production')
if errors:print('\n'.join(errors));sys.exit(1)
print('Environment validation passed; values not displayed')
