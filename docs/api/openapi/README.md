# HSAAI OpenAPI Specifications (Phase 12)

## Available Specs

| Service | Spec File | Swagger UI | Redoc |
|---------|-----------|------------|-------|
| LLM Gateway | [llm-gateway.yaml](./llm-gateway.yaml) | `/docs/llm/swagger` | `/docs/llm/redoc` |
| RAG Engine | [rag-engine.yaml](./rag-engine.yaml) | `/docs/rag/swagger` | `/docs/rag/redoc` |
| Agents | [agents.yaml](./agents.yaml) | `/docs/agents/swagger` | `/docs/agents/redoc` |
| Governance | [governance.yaml](./governance.yaml) | `/docs/governance/swagger` | `/docs/governance/redoc` |
| Safety | [safety.yaml](./safety.yaml) | `/docs/safety/swagger` | `/docs/safety/redoc` |

## Viewing Specs

### Online (Swagger UI)
```bash
# Start Swagger UI container
docker run -p 8081:8080 -e SWAGGER_JSON=/specs/llm-gateway.yaml \
  -v $(pwd)/docs/api/openapi:/specs swaggerapi/swagger-ui
# Open http://localhost:8081
```

### Online (Redoc)
```bash
# Start Redoc container
docker run -p 8082:80 -e SPEC_URL=/specs/governance.yaml \
  -v $(pwd)/docs/api/openapi:/specs redocly/redoc
# Open http://localhost:8082
```

### Validate Specs
```bash
# Install validator
npm install -g @redocly/cli

# Validate all specs
for spec in docs/api/openapi/*.yaml; do
  redocly lint $spec
done
```

## SDK Generation

### Python SDK
```bash
npx openapi-typescript-codegen --input docs/api/openapi/llm-gateway.yaml \
  --output ./sdk/python/llm-gateway --client axios
```

### TypeScript SDK
```bash
npx openapi-typescript docs/api/openapi/llm-gateway.yaml \
  --output ./sdk/typescript/llm-gateway/types.ts
```

### Mobile SDK (used by HSAAI mobile app)
Mobile app imports types directly from these specs:
```typescript
import type { GenerateRequest } from './sdk/llm-gateway-types';
```

## API Changelog

### v1.0.0 (2026-07-04)
- Initial OpenAPI 3.1 specs for 5 services
- All endpoints documented with request/response examples
- Authentication via Bearer JWT (Keycloak OIDC)
- Standard error catalog (VALIDATION_ERROR, UNAUTHORIZED, FORBIDDEN, RATE_LIMITED)
- Pagination via `page` + `per_page` + `total` (where applicable)
- Filtering via query parameters
- Sorting via `sort=field` or `sort=-field` (descending)
- Rate limits: 50-100 req/min per tenant depending on endpoint

## Deprecation Policy

- API versioned via URL prefix (`/v1/`, `/v2/`)
- Breaking changes require new version
- Deprecated endpoints marked with `deprecated: true` in spec
- Deprecated endpoints removed after 6 months
- Migration guide published 3 months before removal

## Authentication Flow

```
1. Mobile/Web → POST /auth/token (Keycloak)
2. Keycloak → returns JWT (contains tenant_id, roles, sub)
3. Client → stores JWT in SecureStore (mobile) or httpOnly cookie (web)
4. Client → sends JWT in Authorization: Bearer header on every request
5. API Gateway → validates JWT with Keycloak
6. API Gateway → forwards request with X-Tenant-Id, X-User-Id, X-Roles headers
7. Backend service → uses headers for RBAC/ABAC check via governance service
```
