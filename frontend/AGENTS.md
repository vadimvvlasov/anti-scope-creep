<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project rules

- All backend calls go through `src/services/api.ts` (types, `ApiError`, HTTP client, mock client, token storage, global 401 handler). No `fetch`/URL building elsewhere — keeps the UI independent of the backend and lets the app run on the mock.
- `VITE_USE_MOCK` (default `true`) selects the in-memory mock in `src/services/mock/`; `VITE_API_URL` targets the real FastAPI backend.
- Frontend tests run with `bun run test` (vitest) and cover the mock service layer.
