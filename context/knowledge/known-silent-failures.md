# Known Silent Failures

Per-tool deceptive responses: what they actually mean and what to do instead.
Add a row whenever a session discovers one (feedback tag: domain-knowledge).

| Tool / call | Deceptive response | Actually means | Correct action |
|---|---|---|---|
| {{tool}} | `{}` | {{e.g. backing service stale — NOT "no results"}} | {{e.g. treat as unknown; check the service}} |
| {{tool}} | `{"message": null}` | {{e.g. write did not persist}} | {{re-read and verify before claiming success}} |

**Capping rule:** an empty response from a deprecated or limited-coverage tool
is "unknown", not "empty". Never present an unknown as a zero.
