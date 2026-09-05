# Adversarial Review

## Overview

Reviews a non-trivial change by dispatching independent reviewers and adjudicating their findings. Exists because self-review of one's own change has a measured poor hit rate: self-review can pass changes where independent reviewers then find defects. Reviewer findings also carry a false-positive base rate, so every finding is verified before it is acted on.

## Parameters

- **change_description** (required): what changed and why
- **areas** (optional): file-boundary areas to scope reviewers to

## Steps

### 1. Establish the baseline and fix the ground truth

Run `python3 context/scripts/validate-wiring.py` and record the result. Declare what the change is supposed to do, and that the WORKING TREE is the ground truth for review.

**Constraints:**
- You MUST record the baseline validator result BEFORE reviewing — because this SOP applies fixes, and pre-existing findings must not be attributed to the change under review.
- You MUST review the working tree, not a stale diff — because outdated diffs produce stale findings.

### 2. Scope reviewers along file boundaries, run them in parallel

Split the change into areas with minimal overlap; dispatch one reviewer per area.

**Constraints:**
- You MUST brief each reviewer with recurring defect classes: checks that cannot fail, fix-command drift, ambient-vs-clean environment assumptions, fail-open behavior where fail-closed is required, environment-specific values in shipped source, and vacuous tests.
- You MUST pass each reviewer the already-found list — because duplicate findings waste adjudication time.

### 3. Verify every finding before acting

Reproduce each finding against the working tree.

**Constraints:**
- You MUST verify each finding — because the false-positive base rate is high enough to plan for.
- You MUST NOT fix an unverified finding — because fixing phantoms introduces real defects.

### 4. Fix, then prove each fix discriminates

Apply fixes for verified findings.

**Constraints:**
- You MUST prove each guard-type fix discriminates: remove the guard and confirm its test fails — because a guard whose absence changes nothing is decoration.

### 5. Re-dispatch after fixing

Run another review round on the fixed tree.

**Constraints:**
- You MUST re-dispatch at least once after fixes — because follow-up rounds often find issues created by previous fixes.
- You SHOULD stop when a round returns only unverifiable or accepted-risk findings.
