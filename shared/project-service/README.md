# shared/project-service

A small background program all four apps talk to: project items, shared named markers, live links between apps, the content-keyed cache, and one jobs queue for the whole machine (heavy jobs take turns on the one GPU and the 16 GB of memory).

Contract: [`CONTRACT.md`](CONTRACT.md). No code yet. The service's own language is chosen when it is built (Stage 2); apps reach it through `rostrum_core`.
