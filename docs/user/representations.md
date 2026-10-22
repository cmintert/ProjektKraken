# Understand attributes, relations and mentions

One historical fact can appear in several forms. Each form serves a different
purpose and may preserve a different claim. Similar wording does not make
those forms synchronize automatically.

## Values and connections

An attribute is a named value on an entry: Northwatch's **Ruler** attribute
names the ruler displayed at a particular time. A relation connects two entries
by identity, direction and meaning, with optional timing. The sample also uses
**rules** relations for its succession. Changing a Ruler value does not by
itself rewrite a rules relation.

This separation allows you to preserve a source's wording even before the
named person has an entry. When you need a connection between two known entries,
use a relation and read its source, meaning and target together. The UI's
**Connections** section presents those relations.

See {ref}`attributes, relations and mentions <help-authoring-representations>`
for the comparison reference and {ref}`create relations <help-relations-create>`
for the procedure. A dated attribute and a timed relation are independent
assertions even when both describe a succession.

## Prose and linked mentions

Plain prose records what you wrote. A wiki link additionally points to an
Event or Entity so you can peek at it or navigate there. A link can remain
unresolved while you write; it need not force you to create the target.

With **Auto-Create Relations from Wikilinks** enabled, saving a resolved link
also records a **mentions** relation. That relation records a reference, not
membership, ownership or participation. Editing an explicit connection does
not rewrite the linked biography. Use {ref}`wiki links <help-writing-links>`
for linking and return-to-writing behavior.

## Decide what you intend to assert

In a fictional example, a biography might quote an old ruler, an attribute
might give the currently displayed title, and a relation might bound an office
to a succession event. Their differences can be intentional. If you intend
them to agree, review each source after a change rather than expecting the
same words to identify one shared fact.
