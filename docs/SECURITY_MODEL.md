# Security model

break FAST is built for a trusted home network (LAN or Tailscale), not the open internet.

- Login is a name and a numeric PIN, stored as a salted scrypt hash.
- Logins are rate-limited with exponential backoff.
- Session tokens are random, kept in memory and sent only in headers, never in URLs. Logging out ends that device's session on the server; a restart logs everyone out.
- Every query is scoped to the logged-in user, with explicit session ownership validation.
- Every request has size limits: text, lists, numbers and whole bodies are bounded, and a request over a limit is refused before it reaches the database or the model.
- Error replies are fixed messages that never include exception text, stack traces or file paths.
- Do not expose the server port to the public internet. Use Tailscale for remote access.

---

Back to the [README](../README.md).
