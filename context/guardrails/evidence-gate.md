# Evidence Gate — Before Any Mutation

Applies to every operation that creates, changes, sends, or deletes anything.
One subject: no mutation is proposed or executed on assumption.

## The gate

Before proposing any mutation:

1. **State the evidence.** What did you verify, and with which tool?
2. **Verify preconditions with the CORRECT tool** — the one that owns that
   fact, not a proxy.
3. **Check ALL inputs.** If the operation touches five resources, verify all
   five. Checking one and assuming the rest is a violation.
4. **Cite the source** of the procedure you are following, as
   `[source: <skill-name> § <section>]`.

## What is NOT evidence

- "This seems like it should work."
- "This might be optional."
- "The previous step probably created it."

If a precondition cannot be verified, say so and stop — do not downgrade the
gate to a hope.

**Steering practice:** when this gate delays a mutation the user expected
immediately, say so and name it ("evidence gate").
