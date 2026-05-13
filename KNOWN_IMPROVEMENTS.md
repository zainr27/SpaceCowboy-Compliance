# Known Improvements

Architectural findings and corpus gaps identified during development.
Resolved items document what was fixed and when.

---

## RESOLVED: Document Diversity in Multi-Query Retrieval

Single-document chunk count was monopolizing the merged candidate pool,
making large documents (e.g., the CubeLab ICD with ~75 chunks) crowd out
smaller spec sheets (e.g., Redwire ADSEP flysheet with ~12 chunks) even
when reranker scored individual chunks comparably.

Fix: added `min_docs` parameter to `retrieve_multi_query` that guarantees
at least 3 distinct documents in the final context window. Greedy
diversification followed by score-based fill of remaining slots.

Resolved: hour ten, during mission agent integration. All four sub-agents
now benefit.

---

## Hardware Coverage Gap: Continuous Cell Culture

Neither ADSEP nor TangoLab claims media exchange / perfusion capability
in their specs. This is a real corpus gap for any protocol requiring
continuous cell culture over multi-day timeframes. The agents correctly
report this rather than fabricating capability, but the system can't
recommend an actually-fitting facility because no flysheet in the corpus
describes one.

Resolution path: ingest specs for BioServe SABL (which the FY25 annual
report describes as supporting cell culture with media exchange), or
acquire the actual NASA Research Hardware Catalog covering cell-culture-
specific bioreactors. Priority before publishing the orchestrator's
output as user-facing.
