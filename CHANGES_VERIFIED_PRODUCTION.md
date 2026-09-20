# HSAAI — Production verification fixes

Additional defects found while validating `HSAAI_v3_UI_Corrected_v3_FIXED.zip` for the full Docker Compose path:

- Declared missing `vault_data` / `vault_audit` volumes.
- Removed unsupported pgvector extension bootstrap from stock `postgres:16` (Qdrant is the selected vector store).
- Added Keycloak realm import at startup and separated browser-visible issuer from Docker-internal JWKS/token URLs.
- Added `hsaai-api` audience mapper to the frontend PKCE client.
- Fixed API gateway CORS for `X-Requested-With`.
- Gateway now converts the httpOnly access-token cookie to an internal Bearer header and forwards it downstream.
- Added gateway auth proxy endpoints and preserved Set-Cookie headers.
- Preserved tenant/workspace claims in auth token verification.
- Added missing RAG document/analytics and Knowledge Governance gateway routes used by the shipped UI.
- Fixed browser API fallbacks from Keycloak port 8080 to API gateway port 8000.
- Made the public PKCE client secret optional in the Next.js code exchange.
- Added a dedicated NVIDIA GPU Compose override for Ollama.
- Reworked `start.sh` so it starts the full Compose model and reports correct Web/Grafana ports.
- Completed required Compose secrets in `.env.example` / `.env.production.example`.

Runtime note: this validation environment does not provide Docker or outbound package-network access, so the 56-container stack could not be launched here. Static Compose contracts, source compilation, available pytest suites, and the dockerless OIDC provider were executed locally.
