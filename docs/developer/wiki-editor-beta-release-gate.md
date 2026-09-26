# Wiki Editor Beta Release Gate

Apply this gate before approving a public ProjektKraken beta. Do not approve the
release while a known save, autosave, or navigation path can move the caret,
lose text, overwrite a newer draft, or resolve a duplicate-name wiki link to
the wrong object. These failures break trust in the primary authoring surface.

The release reviewer must confirm all of the following against the release
candidate:

- [ ] All P0 wiki editor findings are fixed and covered by lifecycle regression
  tests, including temporal Entity autosave, guarded timeline Event navigation,
  Event save acknowledgement, and revision-aware handling of late save responses.
- [ ] The supported Markdown vocabulary is documented and round-trip tested
  through Rich, Source, Save, Reopen, and Export.
- [ ] Duplicate-name wiki-link completion preserves the identity of the
  selected object and persists the intended ID.
- [ ] Formatting actions preserve wiki-link targets and other supported link
  semantics.
- [ ] Unresolved wiki links can be saved and reopened without blocking the
  writer, even if full materialization is deferred.
- [ ] Peek reads references without changing the active editor or selection and
  follows the active theme.
- [ ] Deliberate deferrals, including richer Markdown editing and media previews,
  are documented as product gaps with clear user-visible behavior.

Record the passing tests, manual checks, supported Markdown documentation, and
known deferrals in the release review. A passing test suite alone does not
override a known failure of this gate.

This gate is based on the *Projekt Kraken Wiki Editor UX and Reliability Audit*
dated 23 September 2026. Its finding IDs and remediation order define the P0
scope.
