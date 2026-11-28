# World Relations for ProjektKraken

This pack gives you 63 relation definitions across eight categories. Use the
same vocabulary for a court, a covert operation, a colony, or an everyday
community. The entries in your world give the relations their setting.

## Import into a world

1. Extract this ZIP and open your destination world in Kraken.
2. Go to **Settings → This World → Relation Dictionary → Open Relation Dictionary**.
3. Choose **Import preset…** and open **world-relations.json** for all 63
   definitions, or choose a JSON file under **categories** to import one group.
4. Review the proposed definitions and the number of existing connections that
   use each key. Use **Skip** to leave out an addition. For a conflict, choose
   **Keep existing** if you want to preserve your world's wording, or
   **Replace** to apply the pack's definition to that key.
5. Choose **Import definitions**, then open a definition to verify its forward
   and reverse wording. One Undo action restores the dictionary from before that
   import.

The complete file includes all eight category files. Use the complete file or
the categories you want. Importing copies definitions into the open world.
Importing creates no characters, places, Events, or connections.

## Pick a category

| Category | Use it for |
| --- | --- |
| Authority & allegiance | Rule, command, appointments, representation, and claims to authority |
| Kinship & personal ties | Family, partners, guardians, mentors, confidence, and estrangement |
| Cooperation & conflict | Alliances, rivalry, negotiation, protection, surveillance, and betrayal |
| Obligations & exchange | Debts, funding, supplies, trade, employment, and agreements |
| Place, access & custody | Bases, borders, routes, access, ownership, custody, and hiding places |
| Events & responsibility | Organizers, commissioners, actors, investigators, causes, and harm |
| Knowledge & evidence | Witnesses, records, what people know or suspect, and corroboration |
| Belief & affiliation | Membership, founders, teachers, veneration, initiation, and oaths |

## Choose the relation that answers your question

- **Governs vs. Claims authority over.** A council governs the harbor while a
  claimant disputes its authority. Save both relations if both assertions matter.
- **Owns vs. Holds in custody.** The archive owns a ledger while an investigator
  holds it in custody. From the ledger's side, the second relation reads
  “The ledger is held in custody by the investigator.”
- **Witnessed vs. Involves.** Use **Witnessed** for someone who directly observed
  an Event. Use Kraken's existing **Involves** or **Participated in** keys for
  event participation. An account can also **Corroborate** or **Contradict**
  another account.
- **Member of vs. Sworn to.** Membership records belonging. Allegiance records
  a pledge, including one made to a person outside the group.

Start and end dates can record when authority, custody, or a pledge changes.
A reverse sentence offers another view of the same connection. For a mutual
relation such as **Allied with**, one saved connection is enough.

The pack reuses the keys `member_of`, `parent_of`, `owns`, and `caused`, and
uses the earlier starter's `rules` key for **Governs**. Review those keys in
particular when importing into a world that already uses them.
