# Ticket 04: Verify the Kronos pre-training cutoff

**Status:** Scoped, not filed. Type: research (AFK). From Phase 2 Task 5.

## Question

`CLAUDE.md` says the Kronos pre-training cutoff is "~Dec 2022 (inferred)" and
that 2023-2026 OOS results are therefore clean, while the 2022 part of older
runs (including the canonical 2022-2024 result) may be partly in-sample. Is
the cutoff documented, and what is it exactly?

## Sources (primary only)

arXiv:2508.02739 (section on pre-training data), the Hugging Face model card
for `NeoQuasar/Kronos-small`, and the `shiyu-coder/Kronos` repository.

## Deliverable

A cited Markdown note (use `/research`) stating the cutoff or that it is not
documented. Then update the `CLAUDE.md` bullet and the open item in
`PROJECT_STRUCTURE.md` ("Kronos pre-training cutoff: Unverified").

## Why it matters

If training data overlaps 2023 or later, the "clean OOS" claim in every doc is
affected. Small, independent, cheap.
