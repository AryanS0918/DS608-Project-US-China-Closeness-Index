## Trade-data pipeline

### Tool used

Microsoft 365 Copilot

### Purpose

Generative AI was used to support:

- comparison of candidate merchandise-trade sources;
- interpretation of UN Comtrade API fields and metadata;
- design of the authenticated API collection pipeline;
- debugging of local SSL certificate verification;
- development of resumable local caching;
- identification of inefficient API-call usage;
- redesign of mirror retrieval into anchor-year batches;
- extension of mirror supplementation to all four bilateral flows;
- drafting of validation checks and unit tests; and
- drafting of repository documentation.

### Review and verification

The group did not accept the generated code or methodological
interpretations without review.

The outputs were checked by:

- consulting official UN Comtrade documentation;
- inspecting returned API fields and processing flags;
- reconciling a single-country query with the corresponding global
  query;
- confirming that cached files were reused;
- monitoring API-call limits and redesigning inefficient requests;
- testing reporter and mirror-flow mappings;
- checking for duplicate records and missing ISO identifiers;
- verifying that scores remained between -1 and +1;
- ensuring incomplete records received no score;
- preserving unresolved values as missing rather than zero; and
- running eight automated unit tests.

The group remains responsible for the final code, methodological
choices, data treatment, documentation, and interpretation.