---
name: user-docu
description: Write or revise ProjektKraken user documentation from verified application behavior, preserving contextual Help destinations.
---

# ProjektKraken User Documentation

Read [Documentation Authoring and Maintenance](../../../docs/developer/documentation.md)
before writing. It is the canonical policy for documentation type, editorial
style, terminology, review and acceptance. Do not impose a fixed feature-page
template or create another policy copy.

## Workflow

1. Identify the reader, task, affected release, canonical page and Help IDs.
   Prefer improving the existing authoritative topic.
2. Choose one primary purpose: tutorial, how-to, reference or explanation.
   Keep operational procedures separate from longer conceptual discussion;
   cross-link them. Existing control appendices may remain in their chapters.
3. Read the relevant GUI labels, coordinator/command behavior and tests. Trace
   save/apply/cancel and recovery behavior rather than assuming autosave.
   Domain terms such as Event, Entity and Relation belong in user prose;
   explain them. Implementation classes and Qt plumbing usually do not.
4. Write the preferred route with prerequisites, numbered actions, the action
   that accepts/saves it, and a verifiable result. Explain independent effects,
   limitations and recovery where consequential. Preserve advanced semantics.
5. Preserve topic meanings, explicit and existing heading anchors, excerpts,
   inspection bindings and task links. Keep prose in canonical documentation,
   never widgets. Review changed source fingerprints individually.
6. Run the guide's generation and relevant Help regression checks. Inspect
   the rendered manual and offline Help, including search and affected entry
   points. Structure checks do not establish semantic correctness.
7. Use the linked review and reader-observation forms. Record human prose/live
   Help approval as pending until supplied; never fabricate participant results.

Use Northwatch for maintained introductory examples after checking its generator
and fixture tests. Never imply that a fictional example is saved demo content.
Keep documentation reader rounds separate from the existing empty-world authoring
benchmark. Do not rewrite unrelated developer/reference/release collections during
a user-manual task.
