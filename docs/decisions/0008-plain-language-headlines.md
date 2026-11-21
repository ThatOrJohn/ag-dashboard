# 0008: "This week" headlines are generated from rules, one sentence per source

- **Status:** Accepted
- **Date:** 2026-11-20

## Context
The core value is the "so what" for this week (seed.md). A site publishing a wrong or
alarming sentence hurts more than publishing none.

## Decision
`kad/headline.py` builds the headline for Texas and each home district from fixed rules. Each sentence comes
from one source, carries a topic (drought, rain, burn_bans, cattle, crop:<id>), and is left out when its
source is stale. Drought "held steady" within 2 points, otherwise "eased" or "expanded"; a year ago is
mentioned only when it differs by 10+ points; the D3+ share is mentioned only at 25%+. Crop pace is "ahead
of / behind / in line with" the 5-year average at a 3-point threshold. Persona pages keep only the
sentences for their own sections, in `card_order` order. Every headline ends with "Based on" and the
sources' dates.

## Why
Rules are testable, predictable and can't invent a fact. Calm verbs keep the tone plain (CLAUDE.md). No
language model writes copy.

## Consequences
The wording is formulaic; good enough for a weekly read. New sources need a sentence rule and a topic.
