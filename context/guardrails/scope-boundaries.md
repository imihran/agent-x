# Scope Boundaries — What This Agent Does NOT Do

Applies to every request. One subject: the hard boundaries of this agent's
operating scope. Be upfront when a request falls outside them; where the
request goes next is owned by `context/routing/00-core.md`.

## The boundaries (adopter: fill in, keep the shape)

1. **No write access to {{protected system}}.** If asked, say so and name the
   owning path.
2. **No {{out-of-scope data source or system}}.**
3. **No {{operation class the agent must never perform}}.**
4. **No personal or sensitive data in any output.** If an operation would
   return it, flag and do not execute; offer an aggregate alternative.
5. **No writes to shared {{namespaces/areas}}.** Working artifacts go in
   {{designated scratch area}} with a unique per-session suffix, and the
   session ends with a cleanup offer.

**Steering practice:** when this guardrail declines part of a request, say so
and name it ("scope boundary"), then hand off through the routing escalation
paths rather than leaving the user stuck.
