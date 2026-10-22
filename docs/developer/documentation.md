(documentation-maintenance)=

# Documentation Authoring and Maintenance

**Version:** 1.0 — KRT-105

**Applies to:** User manual, contextual Help, reference documentation, developer documentation, and release guides

**Status:** Adopted contributor policy; manual rollout acceptance is tracked separately.

## 1. Purpose

Projekt Kraken is an expert-level application for writing, organizing, and visualizing changing fictional or historical worlds.

Its documentation must make sophisticated capabilities understandable without oversimplifying them.

A successful manual enables a reader to:

* Discover what Kraken can do.
* Learn a workflow through a realistic example.
* Accomplish a specific task without external assistance.
* Understand why the software behaves as it does.
* Find precise information quickly.
* Recognize mistakes, recover safely, and trust the result.

Documentation is part of the product, not an optional supplement.

**Governing principle:** Use Diátaxis to determine what kind of documentation to write, Google's and Microsoft's style guides to determine how to write it, and observed user performance to determine whether it succeeds.

Accuracy, safety, and clear communication take precedence over completeness, stylistic elegance, or marketing language.

## 2. Documentation architecture — Diátaxis

Every substantial documentation page must have a clearly identified primary purpose.

Diátaxis recognizes four kinds of technical documentation.

| Type | Reader's need | Kraken example |
| -- | -- | -- |
| Tutorial | Teach me | Build a changing kingdom using the Northwatch demo |
| How-to guide | Help me accomplish something | Record a ruler's succession with an uncertain date |
| Reference | Tell me exactly how this works | Relation boundary modes and their effects |
| Explanation | Help me understand | Why viewing time differs from world current time |

A feature may require several document types. They should link to one another instead of duplicating their content.

The four types are editorial classifications. They do not require four new directory trees or an immediate reorganization of every existing file.

### 2.1 Tutorials — Learning by doing

A tutorial is a guided learning experience, not a comprehensive feature description.

It must:

* Start with a concrete, achievable outcome.
* Use a prepared example or an easily reproducible starting point.
* Introduce concepts only when needed for the exercise.
* Guide the reader through a sequence that produces visible results.
* Include checkpoints that confirm successful progress.
* Explain how to recover from likely mistakes.
* End with a result the reader can recognize.

For Kraken, tutorials should preferably use the Northwatch demo world or another maintained example.

A suitable introductory tutorial might establish a kingdom, record a succession, change a border, and inspect the world at different dates.

Do not burden the reader with advanced data structures, alternative methods, or configuration details unrelated to the exercise.

Tutorials must be tested with inexperienced readers.

### 2.2 How-to guides — Completing a task

A how-to guide assumes the reader already has some familiarity with Kraken.

Its title should express a goal.

**Preferred:** Record a change of ruler without an exact date.

**Avoid:** Relation editor operations.

A how-to guide normally contains:

1. A short description of the intended result.
2. Prerequisites or required starting conditions.
3. The recommended sequence of actions.
4. Expected results and any necessary verification.
5. Relevant consequences, limitations, and recovery instructions.
6. Links to deeper explanations or reference material.

Document one preferred route clearly. Describe alternatives when they serve a distinct need, rather than interrupting every procedure with multiple options.

The reader should not need to understand Kraken's implementation architecture to follow a how-to guide.

### 2.3 Reference — Finding exact information

Reference documentation describes the software's existing behavior accurately and systematically.

Examples include:

* Menu actions and keyboard shortcuts.
* Dialog fields and options.
* Date and duration representations.
* Relation meanings and boundary modes.
* CLI commands and arguments.
* Import and export formats.
* Configuration settings.

Reference entries should be concise, neutral, and consistent.

A control explanation should answer:

* What does this control do?
* What does it change?
* What does it leave unchanged?
* Are there important restrictions or prerequisites?
* Where can the reader find the full procedure?

Not every entry needs all five answers. Include only what is relevant.

Control-reference prose must remain accessible through Kraken's contextual Help system.

**Do not substitute a broad tutorial for a precise control reference.**

### 2.4 Explanation — Understanding the model

Explanation pages address concepts, reasons, limitations, and design choices.

They may be longer and more discursive than reference material.

Important subjects for Kraken include:

* Viewing time versus World current time.
* Date precision versus duration.
* Historical states and their source records.
* Attributes versus relations versus wiki mentions.
* Dated geometry versus temporal visibility.
* Deterministic World Context versus AI-generated interpretation.
* Local-first storage and portability.

Explain the conceptual distinction using a consistent example. Diagrams may help where prose cannot express the relationship efficiently.

Explanations should not be overloaded with interface instructions. Link to the relevant how-to guide instead.

(canonical-locations)=

## 3. Canonical sources and organization

Keep the existing repository organization.

| Location | Responsibility |
| -- | -- |
| `README.md` | Product overview, installation, essential navigation |
| `docs/user/` | Tutorials, how-to guides, explanations, user-facing Help |
| `docs/developer/` | Architecture, contributor procedures, engineering contracts |
| `docs/reference/` | Command reference, configuration, generated technical facts |
| `docs/releases/` | Version-specific release information |
| `docs/help-topics.json` | Semantic Help topic registry |
| `docs/help-inspection.json` | Control inspection inventory |
| `archive/documentation/` | Historical material, not current operational guidance |
| `planning/` | Proposals and research, not authoritative user instructions |

These are existing responsibilities, not instructions to reorganize files immediately.

Each fact or procedure should have one authoritative home. Other pages should link to it.

Avoid creating a second source of truth for installation, relation semantics, date interpretation, or world backup behavior.

Only implemented and supported features belong in the current user manual. Planned behavior must be labeled and maintained separately.

Every new Markdown page under `docs/` must be reachable through the Sphinx navigation structure.

### Reader-facing and contextual reference material

A user-manual chapter should present its main instructional content before lengthy reference inventories.

Concise control explanations can remain in the canonical source and be presented separately in navigation, provided all contextual destinations and generated Help behavior are preserved.

Do not physically relocate existing control explanations merely to improve readability until the associated topic and inspection mappings have been updated and verified.

## 4. Editorial voice and language

Kraken documentation should sound like a knowledgeable person explaining a serious tool to another capable person.

### 4.1 Basic rules

* Use plain, idiomatic English.
* Prefer active voice and present tense.
* Address the reader directly where appropriate.
* Use imperative verbs in procedural steps.
* Prefer concrete nouns and actions to abstract descriptions.
* Explain technical terms when first introduced.
* Keep sentences manageable without enforcing arbitrary word limits.
* Use descriptive headings that make sense outside their parent chapter.
* Remove sentences that merely repeat the heading.
* Avoid marketing claims inside procedural documentation.

Use consistent spelling in new documentation. American English may serve as the default house style, but literal UI labels, identifiers, and existing technical terminology must never be altered to match a spelling preference.

### 4.2 Tone

Use a calm, precise, helpful voice.

Do not use promotional phrases such as *revolutionary*, *powerful*, *seamless*, or *effortless* to describe ordinary operations.

Avoid formulaic introductory language, excessive enthusiasm, unnecessary repetition, and conversational filler.

Do not turn reference entries into miniature essays.

When the software has a limitation, state it directly.

When a task can destroy data or change historical assertions, explain the consequences without alarmism.

### 4.3 Terminology

Use one preferred name for each concept and preserve its meaning.

Examples of concepts requiring controlled vocabulary:

* Event
* Entity
* Connection or Relation, according to the defined UI/domain context
* Viewing time
* World current time
* Date precision
* Duration
* Historical state
* Base Geometry
* Timed location
* Route point
* World Context

Use exact application wording when instructing readers to interact with the interface.

For example, do not write **Tools → AI Settings** if the current application uses **Settings → AI Search Index and Settings…**.

A conceptual term and its UI label may differ. Explain the relationship explicitly rather than silently using them interchangeably.

## 5. Writing procedures

Follow Google Developer Documentation and Microsoft Style Guide conventions.

### 5.1 Procedure rules

A procedure should:

1. State the intended outcome.
2. Identify the starting location when necessary.
3. Use numbered steps in execution order.
4. Start each step with an action.
5. Describe one significant action per step.
6. Use the actual names of controls and menu commands.
7. Include the action that commits, applies, or saves the result.
8. State the expected result.
9. Explain important exceptions and recovery routes.

Small related actions may be combined when doing so improves clarity.

Do not repeat the same procedure across several chapters. Link to its canonical location.

### 5.2 Example

**Weak:**

"Relations can be configured through the relation interface, which provides several options for temporal boundaries and relationship behavior."

**Better:**

"To record when a ruler's reign began, open the ruler's Connections section and edit the relevant relation. Under Timing, set the start boundary to the succession Event. Apply the change.

The relation now follows that Event's date, including its recorded uncertainty."

The second example identifies a task, shows the relevant action, and explains the result.

Any exact menu or field wording used in a published procedure must be verified against the current application.

### 5.3 Results and consequences

For consequential actions, distinguish:

**What changes:** The new historical state, relation, world setting, or document membership.

**What stays unchanged:** Other records, unrelated relations, original geometry, or saved content.

**How to recover:** Cancel, Undo, restore a source value, or use a verified backup, as applicable.

These distinctions are especially important in Kraken because different representations may refer to the same historical fact without being automatically synchronized.

## 6. Examples, screenshots, and diagrams

Examples must serve understanding rather than decoration.

Use consistent, realistic worldbuilding scenarios.

Prefer the Northwatch demo world for maintained introductory material. Its events, characters, places, and historical transitions should remain consistent across related tutorials.

A fictional example may be used to explain a concept without depending on a particular demo version, but it must not be presented as an existing saved world state unless verified.

### Screenshots

Use screenshots when they clarify:

* Spatial layout.
* The location of non-obvious controls.
* Selection and editing states.
* Timeline or map visual representations.
* Before-and-after results.

Screenshots must reflect the documented release and use readable text.

Crop irrelevant surroundings while retaining enough context to identify the interface.

Use diagrams for conceptual relationships, such as the difference between a source Event, a dated Entity change, and a Relation bound to that Event.

Provide meaningful alternative text. Do not rely on color alone to communicate a distinction.

Avoid screenshots for simple instructions that can be expressed accurately in one sentence.

## 7. Contextual Help preservation contract

**F1, Shift+F1, Ctrl+Shift+F1, offline Help, and their existing semantic mappings are protected application functionality.**

Documentation improvements must not weaken or remove them.

### 7.1 Required behavior

**F1 — Help for current task**

Opens the appropriate Help topic for the active control, dialog, panel, or task. The existing fallback to the manual must remain available when no specific topic applies.

**Shift+F1 — Explain pointer target**

Explains the supported control under the pointer without clicking it, activating it, or substituting an unrelated focused control.

**Ctrl+Shift+F1 — Explain focused target**

Explains the focused control or active highlighted menu action.

**Help → Inspect control**

Preserves the inspection workflow, including non-activating pointer selection, popup behavior, and links to the corresponding task.

**Help search**

Continues to search the packaged manual and open valid task and reference destinations.

**Offline Help**

Remains readable without an internet connection, using the content bundled with the matching release.

### 7.2 Semantic identity preservation

Existing IDs in `docs/help-topics.json` should be treated as stable semantic identifiers.

A documentation reorganization may move or rename a source page, but it must preserve the correct target for each existing ID.

The inspection inventory in `docs/help-inspection.json` must continue to resolve each supported control to its intended explanation and task.

Do not:

* Delete an established anchor without a verified replacement.
* Redirect a specific explanation to a generic chapter merely because the latter exists.
* Reassign an established topic ID to a different meaning.
* Refresh source fingerprints in bulk simply to silence a validation failure.
* Store explanation prose independently inside individual widgets.
* Replace a contextual explanation with a broken link or an unrelated fallback.

New or changed controls require an explicit inspection inventory review.

### 7.3 Preservation of authoring state

Invoking, reading, navigating, or dismissing Help must not unexpectedly:

* Save or discard pending writing.
* Change caret position or text selection.
* Change the currently selected Event or Entity.
* Move the timeline playhead.
* Commit or cancel unfinished map edits.
* Apply an unfinished relation.
* Exit Focus writing.
* Trigger the inspected control.

Existing keyboard focus restoration, Help history, Escape precedence, and modal safeguards must remain intact.

### 7.4 Editorial relationship between Help and the manual

One canonical topic should serve both contextual Help and ordinary manual navigation where practical.

Control inspection provides the concise explanation. F1 provides task-oriented assistance. The manual offers broader procedures and conceptual material.

An editor may improve wording or restructure a page, but must verify the resulting experience through both the manual and the application's Help entry points.

### 7.5 Release blocker

A documentation change that breaks an established Help destination, misidentifies a control, prevents offline Help from opening, or causes Help to mutate the user's work must block release.

No documentation restructuring is exempt from this rule.

(update-rules)=

(authoring-help-checklist-for-feature-changes)=

## 8. Documentation development workflow

Documentation changes should follow the same disciplined process as application changes.

Update documentation with changes to visible routes, labels, shortcuts or workflows;
saved data and portability; commands, undo, threading or coordination contracts;
setup, testing, packaging and release; or CLI/configuration behavior. Identify the
affected authoring contracts (1–9 and 11), keyboard ownership and preserved context
when reviewing feature Help. Developer pages may name implementation classes when
needed to explain an engineering contract; user procedures should not require them.

### Stage 1 — Identify the reader's need

Record:

* Intended audience.
* Task or concept.
* Documentation type.
* Existing canonical page.
* Affected application version.
* Affected contextual Help topics.

### Stage 2 — Verify the software

Inspect the current application implementation, UI labels, and related tests before writing operational instructions.

Do not infer current behavior from archived documents, old screenshots, Linear proposals, or previous release notes.

Where implementation and existing documentation disagree, investigate the discrepancy. Do not silently choose one.

### Stage 3 — Draft or revise the content

Use the appropriate Diátaxis structure and the editorial rules in this guide.

Prefer improving an existing authoritative topic over creating duplicate content.

Preserve existing semantic Help identities.

(build-locally)=

(commands)=

### Stage 4 — Verify technical integration

Use the current repository commands, including:

```text
python -m scripts.check_help_inspection
python -m scripts.build_help
python docs/generate_schema_docs.py --check
python -m sphinx -n -W --keep-going -b html docs docs/_build/html
```

Run the relevant current Help, Qt, navigation, and inspection regression tests for the affected surfaces.

The complete current release-preflight requirements remain authoritative. These commands are not a substitute for those requirements.

### Stage 5 — Review the rendered output

Inspect the generated manual and the offline Help presentation.

Verify:

* Headings and navigation.
* Links and anchors.
* Search results.
* Code examples and tables.
* Screenshots and accessibility information.
* Control excerpts.
* Related-topic destinations.
* Display at supported window sizes.

A successful Sphinx build establishes structural correctness, not editorial quality.

### Stage 6 — Human review

A reviewer must check that the prose is accurate, understandable, and consistent with the intended reader's knowledge.

For material affecting contextual Help, review the explanation using the actual application whenever practical.

Record the reviewer, source revision, affected topics, corrections, and approval.

### Stage 7 — Deliver with the feature

When an application change modifies documented behavior, update the corresponding documentation as part of the feature's delivery.

Do not postpone essential documentation corrections to an unspecified future release.

## 9. Usability testing — Proving that the manual works

Documentation quality must be assessed through actual tasks, not just readability scores or build success.

### 9.1 Testing audiences

Use two distinct reader groups.

**New users:** Authors and game masters who understand worldbuilding but have little experience with Kraken.

**Experienced users:** People familiar with Kraken's general workflow who need accurate assistance with specialized operations.

A small group of three to five readers per relevant testing round is a practical starting point for discovering qualitative problems. It is not sufficient for precise statistical estimates of usability.

### 9.2 Suggested task scenarios

Use maintained world data and repeatable starting states.

| Scenario | What to evaluate |
| -- | -- |
| Create an Event dated only to a year | Whether the reader understands date precision |
| Record a disputed succession | Whether Help explains chronology and uncertain relation boundaries |
| Change a historical border | Whether the reader distinguishes dated geometry from visibility |
| Connect an Entity to an Event | Whether the correct relation direction is understood |
| Recover from an unfinished edit | Whether safeguards and Help are understandable |
| Find a specific control with Shift+F1 | Whether the reference explanation is immediately useful |

Include both unassisted and Help-assisted tasks.

For F1 testing, invoke Help from the actual working context rather than navigating directly to the manual.

### 9.3 Observations

Record for each task:

* Completion or failure.
* Time needed.
* Documentation entry point used.
* Whether the correct topic was found.
* Incorrect actions or misunderstandings.
* Assistance required.
* Whether the final saved result is correct.
* Whether the reader understood the consequences.

Use a consistent observation form so results can be compared across releases.

Do not treat a task as successful solely because the participant reports success. Where possible, verify the resulting world data.

### 9.4 Success criteria

All existing mapped Help entry points must continue to resolve correctly.

There must be no documentation-induced data loss, false description of destructive behavior, or Help-triggered mutation.

For reader-performance measurements, establish a baseline before imposing numerical release thresholds.

A reasonable initial aspiration is for at least four of five representative newcomers to complete each essential introductory task without external coaching. Treat that as a provisional product target, not an established industry standard or a substitute for larger validation.

Failures should create specific documentation or UI issues. A task may fail because a feature is hard to discover even when its documentation is correct.

Keep those diagnoses separate.

## 10. Documentation acceptance checklist

Use this checklist when reviewing documentation changes.

### Content

- [ ] The page has an identifiable Diátaxis purpose.
- [ ] The reader's task or information need is clear.
- [ ] Claims describe implemented behavior.
- [ ] Terms and interface labels are consistent.
- [ ] Examples are correct and reproducible.
- [ ] Procedures include expected results.
- [ ] Data-changing operations explain their consequences.
- [ ] Relevant safety and recovery information is present.

### Navigation and Help

- [ ] Existing topic IDs retain their intended meanings.
- [ ] F1 opens the correct topic.
- [ ] Shift+F1 and Ctrl+Shift+F1 work for affected controls.
- [ ] Control inspection remains non-activating.
- [ ] Related-topic links and search destinations work.
- [ ] Offline Help builds and opens successfully.
- [ ] Reading Help preserves authoring context.

### Quality assurance

- [ ] Documentation generation and strict Sphinx pass.
- [ ] Relevant inspection and application regressions pass.
- [ ] Rendered documentation has been reviewed.
- [ ] Required human approval is recorded.
- [ ] Relevant user tasks have been tested or explicitly scheduled for acceptance.
- [ ] The documented release and installation instructions are correct.

An automated check may verify a link, command, or declared label. It cannot replace human judgement about explanation quality or task comprehension.

## 11. Maintaining the standard

This guide is the editorial policy for documentation.

Existing architecture and Help-maintenance contracts remain authoritative for implementation details. This page is the canonical policy. Contributor and agent workflows link here instead of maintaining independent editorial rules.

Review the guide whenever a significant change occurs in:

* Documentation organization.
* Offline Help architecture.
* Supported platforms.
* Editorial terminology.
* Documentation tooling.
* User-testing practice.

Changes should be explicit and justified. Avoid large-scale stylistic rewrites that create unnecessary version-control churn without improving reader outcomes.

### AI-assisted documentation

AI may draft, edit, compare, and identify inconsistencies in documentation.

However, AI-generated documentation must not be treated as verified solely because it sounds plausible.

Require source-code verification for operational claims, explicit review of Help mappings, and human approval for new or substantially revised user-facing explanations.

Do not fabricate UI controls, menu locations, feature availability, screenshots, or testing results.

## 12. Editorial quality standard

The desired outcome is documentation that is:

**Accurate:** It describes what Kraken actually does.

**Findable:** Readers can reach the answer through navigation, search, F1, or control inspection.

**Understandable:** Readers can build a correct mental model without studying the implementation.

**Actionable:** Procedures produce a recognizable, verifiable result.

**Trustworthy:** Limitations, uncertainty, persistence, and recovery are explained precisely.

**Pleasant to read:** Prose is economical, examples are meaningful, and the reader does not have to fight the documentation to learn the software.

A documentation page is finished when it serves its intended reader successfully—not merely when it contains all available information.

---

## References and editorial authorities

1. **Diátaxis — Daniele Procida.** Documentation types and information architecture. [https://diataxis.fr/](<https://diataxis.fr/>)
2. **Google Developer Documentation Style Guide.** Editorial voice, writing conventions, accessibility, and procedures. [https://developers.google.com/style](<https://developers.google.com/style>)
3. **Google — Procedures.** Instructions for writing actionable steps. [https://developers.google.com/style/procedures](<https://developers.google.com/style/procedures>)
4. **Microsoft Writing Style Guide — Writing step-by-step instructions.** [https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions](<https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions>)
5. **Nielsen Norman Group — Help and Documentation.** Usability principles for contextual assistance and documentation. [https://www.nngroup.com/articles/help-and-documentation/](<https://www.nngroup.com/articles/help-and-documentation/>)
6. **John M. Carroll and colleagues — The Minimal Manual.** Foundational research on learning software through meaningful tasks and recoverable exploration. [https://research.ibm.com/publications/the-minimal-manual](<https://research.ibm.com/publications/the-minimal-manual>)

**Projekt Kraken implementation references**

* `docs/developer/documentation.md`
* `docs/help-topics.json`
* `docs/help-inspection.json`
* `docs/user/index.md`
* `scripts/build_help.py`
* `scripts/check_help_inspection.py`
* Existing Help, inspection, Sphinx, and packaged Windows acceptance tests.

## Maintaining interface inspection

The inspection controller owns both explanation chords: Shift+F1 hit-tests the
pointer without falling back to keyboard focus; Ctrl+Shift+F1 explains focus or
the active menu action. Claim shortcut overrides in that dispatcher, without
additional QAction/QShortcut bindings. Retain native What's This pointer mode,
popup rendering and task links. Test complete chords through window-level input
so releases, modal blocking and Escape cannot leak into authoring operations.

`docs/help-inspection.json` is the finite inspection inventory. Each declaration
names its source symbol, semantic control identity, canonical excerpt target and
task topic. Feature constructors attach only `meaning|topic|excerpt` metadata with
`declare_inspection`; widgets never contain the explanation prose. Shared menu
descriptors use operation IDs, and default actions/overflow proxies retain their
original control meaning. Form labels use field associations, never text matching.

When behavior, a handler, field, action or visible wording changes:

1. Read the affected control and its connected operation. Update its short
   canonical paragraph and task if the purpose or consequences changed.
2. Check equivalent instances, labels, menu/overflow routes and intentional
   exemptions. Add a declaration or a reasoned factory exemption for new controls.
3. Run `python -m scripts.check_help_inspection`. A changed reviewed symbol must
   receive a Help-impact review. Record the reviewed source fingerprint and a
   specific explanation of corrections, or why the existing prose remains true.
   Do not refresh fingerprints in bulk merely to pass the check.
4. Build Help and inspect the generated paragraph, direct search destination and
   task link. Record human prose approval before publishing new reference text.

Fingerprints use normalized Python syntax, ignoring comments and layout. They
are change prompts, not proof that prose matches behavior. The native-factory
scan covers the enumerated Qt input constructors; custom widgets, JavaScript
controls and new domain dependencies still need explicit feature review. The
checker is read-only and is included in preflight and the static CI gate.

## Review forms and rollout records

Use the [documentation review form](documentation-review.md) for source, rendered,
and human review, and the [reader-testing protocol](documentation-reader-testing.md)
for task observations. The [KRT-105 rollout record](../ux/evidence/krt105/README.md)
tracks the manual revision and outstanding acceptance. Existing authoring contracts
and release preflight remain authoritative for implementation and delivery.

