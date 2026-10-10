# @frutti/api

TypeScript client for the backend API, generated from its OpenAPI schema.

- `openapi.yaml`: the schema, written by the backend (`manage.py spectacular`).
- `src/generated/`: functions, TanStack Query hooks, types and Zod schemas made by orval. Never edit.
- `src/http.ts`: the transport every generated function uses (session cookie, CSRF token, `ApiError`).
  Written by hand.

After changing an endpoint or a serializer, run `make gen-api` and commit the result. CI fails when the
committed client does not match the backend.
