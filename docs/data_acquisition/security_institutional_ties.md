# Security Institutional Ties: Data Acquisition and Construction

## Purpose

This component measures verified formal security cooperation between each project country and the United States or China. It complements SIPRI arms-transfer data, which measure operational defence-procurement orientation.

## Source hierarchy

Use sources in this order:

1. treaty depositaries and official organisation membership registers;
2. official government treaty texts, designation notices, and joint statements;
3. official government or organisation historical summaries;
4. reputable secondary research only for unresolved interpretation, never as the sole basis for baseline membership where an official source exists.

The original `US-China Index Treaties.xlsx` workbook is retained as a research register and discrepancy-comparison input. The production candidate is built from `security_arrangement_membership_register.csv`.

## Unit of observation

One register row represents one verified country-arrangement membership spell. The annual panel expands each spell from `start_year` through `end_year`, inclusive.

## Depth taxonomy

- `3`: alliance-level or mutual-defence commitment.
- `2`: formal and durable security cooperation, including intelligence, defence technology, military-information, recognised security status, or bilateral security-cooperation agreements.
- `1`: structured security participation without binding mutual defence.
- `0`: observed no qualifying relationship under the reviewed baseline scope.

The headline score is the maximum verified depth in a country-anchor-year divided by three. Supporting arrangements are retained but are not added together in the baseline.

## Baseline arrangement rules

- NATO membership uses official accession years and depth `3`.
- Rio Treaty membership uses effective membership spells and currently receives provisional depth `3`; depth `2` remains a sensitivity option.
- Major Non-NATO Ally status receives depth `2`, unless a separate mutual-defence treaty supports depth `3`.
- Five Eyes receives depth `2`.
- AUKUS receives depth `2` from 2021.
- Quad receives depth `1` for 2007–2008 and from 2017 onward. The 2004 tsunami-response coordination is treated as a precursor.
- US–India GSOMIA receives depth `2`.
- The China–DPRK Treaty of Friendship, Cooperation and Mutual Assistance receives depth `3`.
- Full SCO membership receives depth `1`. Observer and dialogue-partner statuses are omitted from the baseline.
- The China–Solomon Islands Security Cooperation Framework receives depth `2` from 2022.
- Generic strategic partnerships, ordinary military visits, exercises, and arms purchases are excluded. Arms transfers are measured separately through SIPRI.

## China-side asymmetry

The construction does not require the United States and China to have equivalent numbers or types of arrangements. China has historically preferred partnerships and non-bloc security cooperation to US-style alliance networks. The source audit therefore checks completeness within an anchor-neutral institutional taxonomy rather than imposing numerical symmetry.

## Country universe

Historical entities that do not exist during 2004–2025 are excluded. Special, non-sovereign, or policy-dependent entities are reported separately pending an index-wide entity policy. Anchor self-relations are excluded.

## Corrections and audit trail

The revised notebook exports a workbook-versus-register discrepancy audit. The verified register controls the candidate; the original workbook value is never silently rewritten.

Known correction families include:

- NATO accession dates and the erroneous Honduras membership;
- reversed Rio Treaty withdrawal periods;
- Quad institutional phases;
- AUKUS start year;
- omitted Major Non-NATO Allies;
- replacement of the generic China treaty-ally category with the named China–DPRK treaty;
- addition of the China–Solomon Islands security agreement.

## Update procedure

1. Update official membership spells in the normalized register.
2. Record the source URL and a concise source note.
3. Rerun Notebook 12.
4. Review discrepancy, country-universe, source-completeness, and method-sensitivity outputs.
5. Productionise only after unresolved evidence gaps and entity-policy questions are cleared.

## Known limitations

- Rio Treaty legal commitment may not equal NATO operational depth; its depth remains subject to sensitivity review.
- The China-side register is intentionally narrower and should be revisited as additional formal bilateral security agreements are verified.
- The component measures formal institutions, not informal alignment, exercises, arms procurement, or diplomatic rhetoric.
