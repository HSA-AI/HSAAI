#!/usr/bin/env python3
"""Create a new production configuration; existing settings are never overwritten."""
import argparse,json,os,secrets
from pathlib import Path
from urllib.parse import urlsplit

def main():
    p=argparse.ArgumentParser();p.add_argument('--app-url',required=True);p.add_argument('--identity-url',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
    for value in (a.app_url,a.identity_url):
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:p.error('Use HTTPS origins without paths or credentials')
    root=Path(__file__).resolve().parents[1];target=Path(a.output_dir).resolve();target.mkdir(parents=True,exist_ok=True)
    envpath,realmpath=target/'.env.production',target/'hsaai-realm.json'
    if envpath.exists() or realmpath.exists():p.error('Choose a new directory: existing configuration is preserved')
    app,identity=a.app_url.rstrip('/'),a.identity_url.rstrip('/')
    env={'HSAAI_APP_ENV':'production','APP_ENV':'production','DEBUG':'false','HSAAI_ROLE_CLIENT_IDS':'hsaai-api','FIELD_ENCRYPTION_ENABLED':'true','ENCRYPTION_SALT_PATH':'/data/encryption.salt','ENVIRONMENT':'production','APP_PUBLIC_URL':app,'KEYCLOAK_PUBLIC_URL':identity,'CORS_ALLOW_ORIGINS':app,'KEYCLOAK_ISSUER':identity+'/realms/hsaai','KEYCLOAK_AUDIENCE':'hsaai-api','KEYCLOAK_CLIENT_ID':'hsaai-frontend','KEYCLOAK_REALM_FILE':str(realmpath),'POSTGRES_USER':'hsaai','POSTGRES_DB':'hsaai','HSAAI_COOKIE_SECURE':'true','AUTH_REQUIRED':'true','VERIFY_KEYCLOAK_AUDIENCE':'true','ALLOW_DEV_AUTH':'false','ALLOW_DEV_RBAC':'false','ALLOW_EXTERNAL_AI':'false','ALLOW_EXTERNAL_APIS':'false','INTERNAL_ONLY_MODE':'true','LOCAL_LLM_MODEL':'qwen2.5:7b-instruct','RAG_ANSWER_MODEL':'qwen2.5:7b-instruct','EMBEDDING_PROVIDER':'sentence-transformers','EMBEDDING_MODEL':'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2','USE_ALEMBIC':'true','RUN_MIGRATIONS_ON_STARTUP':'false'}
    for key in ['POSTGRES_PASSWORD','APP_DB_PASSWORD','MIGRATION_DB_PASSWORD','JWT_SECRET','DATA_ENCRYPTION_KEY','SESSION_SECRET','AUDIT_HMAC_KEY','KEYCLOAK_ADMIN_PASSWORD','MINIO_ROOT_PASSWORD','KEYCLOAK_DB_PASSWORD','MLFLOW_DB_PASSWORD','NEO4J_PASSWORD','GRAFANA_PASSWORD','GRAFANA_ADMIN_PASSWORD']:env[key]=secrets.token_hex(32)
    realm=json.loads((root/'infrastructure/keycloak/hsaai-realm.json').read_text());realm['sslRequired']='external';realm['bruteForceProtected']=True
    for client in realm.get('clients',[]):
        if client.get('clientId')=='hsaai-frontend':
            client.update(redirectUris=[app+'/api/auth/callback'],webOrigins=[app],rootUrl=app,baseUrl=app)
            client.setdefault('attributes',{})['post.logout.redirect.uris']=app+'/*'
            for claim in ['tenant_id','workspace_id']:
                client.setdefault('protocolMappers',[]).append({'name':claim,'protocol':'openid-connect','protocolMapper':'oidc-usermodel-attribute-mapper','consentRequired':False,'config':{'user.attribute':claim,'claim.name':claim,'jsonType.label':'String','access.token.claim':'true','id.token.claim':'false','userinfo.token.claim':'true'}})
    roles=realm.setdefault('roles',{}).setdefault('realm',[]);existing={r['name'] for r in roles}
    for name in ['hsaai_admin','knowledge_admin','document_reviewer','document_uploader','department_manager','ai_user','auditor','executive']:
        if name not in existing:roles.append({'name':name,'description':'HSAAI application role; assign explicitly'})
    realm['users']=[]
    with envpath.open('x') as f:f.write('# Private deployment settings; do not commit.\n'+''.join(k+'='+v+'\n' for k,v in env.items()))
    os.chmod(envpath,0o600)
    with realmpath.open('x') as f:json.dump(realm,f,ensure_ascii=False,indent=2)
    print('Configuration created. Provision TLS, users, tenant attributes and offline model volumes before startup.')
if __name__=='__main__':main()
