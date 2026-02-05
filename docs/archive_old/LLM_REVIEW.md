---
**Project:** ProjektKraken  
**Document:** LLM Integration Comprehensive Review  
**Last Updated:** 2026-01-14  
**Reviewer:** AI Assistant  
**Version:** v0.6.0+  
---

# LLM Integration Comprehensive Review

## 1. Executive Summary

ProjektKraken has implemented a production-ready, multi-provider LLM system supporting semantic search (embeddings) and text generation. The architecture prioritizes local-first operation with LM Studio as default, plus cloud fallbacks (OpenAI, Google Vertex AI, Anthropic).

**Strengths:**
- Strong `Provider` ABC abstraction  
- Local semantic search with deterministic indexing
- Streaming generation in Qt UI via `GenerationWorker`
- RAG support with top-k retrieval (`{{RAG_CONTEXT}}`)
- Comprehensive CLI tools
- QSettings persistence + env fallback

**Critical Gaps:**
1. **RAG condensation** (2000-char chunks → context bloat)
2. **Structured outputs** (free-text → manual parsing)
3. **Entity deduplication** (no registry → duplicates)
4. **Consistency validation** (no timeline checks → paradoxes)
5. **Prompt infrastructure** (no versioning/templates)
6. **Provenance** (RAG sources hidden)
7. **Testing** (no LLM output validation)
8. **Audit security** (no redaction → data leakage)

**Verdict:** Production-ready for basic use, but **needs structured outputs, RAG condensation, consistency checks** for reliable AI worldbuilding.

---

## 2. Scope & Methodology

**Files Inspected (with absolute paths):**

Core:
- `/home/runner/work/ProjektKraken/ProjektKraken/src/services/llm_provider.py`
- `/home/runner/work/ProjektKraken/ProjektKraken/src/services/providers/*.py`

UI:
- `/home/runner/work/ProjektKraken/ProjektKraken/src/gui/widgets/llm_generation_widget.py`
- `/home/runner/work/ProjektKraken/ProjektKraken/src/gui/widgets/entity_editor.py`
- `/home/runner/work/ProjektKraken/ProjektKraken/src/gui/dialogs/ai_settings_dialog.py`

CLI & Docs:
- `/home/runner/work/ProjektKraken/ProjektKraken/src/cli/index.py`
- `/home/runner/work/ProjektKraken/ProjektKraken/docs/LLM_INTEGRATION.md`
- `/home/runner/work/ProjektKraken/ProjektKraken/docs/SEMANTIC_SEARCH.md`
- `/home/runner/work/ProjektKraken/ProjektKraken/README.md`

---

## 3. Current Implementation Summary

### Provider Abstraction
- **Interface:** `Provider` ABC with `embed()`, `generate()`, `stream_generate()`, `health_check()`, `metadata()`
- **Factory:** `create_provider(id, world_id, **overrides)` → loads from QSettings + env vars
- **Implementations:** LM Studio (default), OpenAI, Google Vertex AI, Anthropic Claude
- **Resilience:** Circuit breaker (5-failure threshold, 60s cooldown), 3 retries with exponential backoff

### UI Integration  
- **Widget:** `LLMGenerationWidget` collapsible panel in entity/event editors
- **Controls:** Provider combo, max tokens (50-4096), temperature (0-200%), RAG checkbox + top_k (1-20)
- **Workflow:** Custom prompt → Generate button → `GenerationWorker` thread → `text_generated` signal → Append to description

### System Prompt
```python
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert fantasy world-builder... "
    "Time is float: 1.0 = 1 day..."
)
```
- Stored in QSettings as `ai_gen_system_prompt`
- Customizable via AI Settings dialog
- **No versioning or template system**

### RAG Helper
`perform_rag_search(prompt, db_path, top_k)`:
1. Query SearchService with first 200 chars of prompt
2. Retrieve top_k results (default 3)
3. Extract descriptions from `text_content` field
4. Truncate each to 2000 chars
5. Format as `### World Knowledge (RAG Data):\n**Name** (Type):\n<description>...`
6. Inject via `{{RAG_CONTEXT}}` placeholder or prepend

**No condensation:** Concatenates raw text (3 × 2000 = 6000 chars)

### Semantic Search
- **SearchService:** Indexes entities/events, stores float32 BLOBs (normalized vectors)
- **Text format:** `Name: X\nType: Y\nTags: ...\nDescription: ...\nattr: val...`
- **Change detection:** SHA-256 hash of text content
- **CLI:** `rebuild`, `query`, `index-object`, `delete-object`

---

## 4. Observed Gaps and Risks

### 4.1. Insufficient RAG Condensation
**Cause:** Concatenates 2000-char descriptions without summarization  
**Harm:** Context bloat (6000 chars for top_k=3), irrelevant details, slower/costlier generation  
**Example:** "Wizard's personality" → 6000 chars (backstory + tower + mentor event), only 10% relevant

### 4.2. Lack of Structured Outputs
**Cause:** `generate()` returns `{"text": str}`, no JSON schema validation  
**Harm:** Unparseable data, manual extraction, hallucination-prone  
**Example:** "Generate NPC" → "The character's name is Eldric..." (prose) not `{"name": "Eldric"}`

### 4.3. No Entity Deduplication
**Cause:** No DB lookup before inserting generated entities  
**Harm:** Duplicates ("Gandalf the Grey" vs "Gandalf the Gray"), lore fragmentation  
**Example:** DB has "King Arthur" → generates "King Arthur" → duplicate entity

### 4.4. Missing Consistency Checks
**Cause:** No validation of timeline logic, circular relations  
**Harm:** Impossible genealogies (born after death), paradoxical events (cause after effect)  
**Example:** Character born year 100 fights in War of year 80 → stored without error

### 4.5. Limited Prompt Infrastructure
**Cause:** Single `DEFAULT_SYSTEM_PROMPT` constant, no versioning  
**Harm:** Inconsistent output, hard to iterate, no few-shot learning  
**Example:** Users manually craft "Generate JSON with..." every time

### 4.6. No LLM Output Tests
**Cause:** No integration tests for schema/prompt regression  
**Harm:** Silent quality degradation, API changes undetected  
**Example:** Provider API change breaks parsing → KeyError → no CI catch

### 4.7. Limited Provenance
**Cause:** RAG results in prompt but not shown to users  
**Harm:** Reduced trust, no source attribution, missed relations  
**Example:** "Staff of Ages" from RAG → user unaware → no link created

### 4.8. Audit Log Data Leakage
**Cause:** Optional logging, no redaction, plaintext  
**Harm:** Sensitive lore exposed, PII leakage, compliance risk  
**Example:** Logs "Secret NPC: villain, real name Alice" → compromised

---

## 5. Prioritized Recommendations

### Quick Wins (1-3 days, Low Risk)

**5.1. Externalize Prompt Templates**  
- Move to `assets/templates/system_prompt_v1.txt` with metadata header
- Create `PromptLoader` class for versioned loading
- **Tests:** `test_prompt_loader_loads_v1()`, `test_lists_templates()`

**5.2. Add Few-Shot Examples**  
- Create `few_shot_entity.txt`, `few_shot_location.txt` (2-3 examples each)
- Prepend to prompts for structured generation
- **Tests:** `test_few_shot_loads()`, `test_injection()`

**5.3. Add Provenance Metadata**  
- Return `{"context": str, "sources": List[Dict]}` from RAG
- Display "Sources: Entity A, Event B" in UI below generated text
- **Tests:** `test_rag_returns_sources()`, `test_ui_displays_sources()`

**5.4. Add JSON Schema Validation**  
- `validate_json_output(text, schema) -> (success, data, error)`
- Catch parse errors early, enable retry logic
- **Tests:** `test_validates_valid()`, `test_rejects_invalid()`, `test_checks_keys()`

---

### Medium-Term (1-2 weeks, Medium Risk)

**5.5. Implement RAG Condensation**  
- `condense_rag_chunks(chunks, max_tokens=100)` → LLM summarization per chunk
- Reduce 2000-char chunks to 100-token summaries
- **Tests:** `test_reduces_length()`, `test_preserves_facts()`, `test_empty()`

**5.6. Structured Output Enforcement**  
- `structured_generate(prompt, schema)` → function-calling or post-validation + retry
- Use OpenAI/Anthropic native APIs, fallback to validation
- **Tests:** `test_with_function_calling()`, `test_fallback_retries()`, `test_raises()`

**5.7. Entity Registry + Deduplication**  
- `EntityRegistry.find_similar(name, threshold=80)` → fuzzy matching (fuzzywuzzy)
- Show merge dialog before creating similar entity
- **Tests:** `test_finds_exact()`, `test_finds_fuzzy()`, `test_ignores_dissimilar()`

**5.8. Consistency Checker**  
- `ConsistencyChecker` with `check_birth_death_order()`, `check_event_dates()`, `check_circular_relations()`
- Surface warnings in UI before save
- **Tests:** `test_detects_birth_after_death()`, `test_negative_duration()`, `test_circular()`

---

### Long-Term (1-2 months, Higher Risk)

**5.9. CI Tests + Regression Prompts**  
- `tests/integration/test_llm_generation.py` with fixed prompts
- Assert schema conformance, key fields present
- **Tests:** `test_character_schema()`, `test_location_description()`, `test_rag_injection()`

**5.10. Telemetry Opt-In**  
- Track accept/reject rate, generation time, token usage
- Store in local SQLite `llm_telemetry` table
- **Tests:** `test_logs_generation()`, `test_acceptance_rate()`

**5.11. Multi-Provider Fallback**  
- `FallbackProvider([("lmstudio", 1), ("openai", 2)])` → try in priority order
- Failover on health_check or circuit breaker
- **Tests:** `test_tries_all()`, `test_succeeds_second()`, `test_raises_all_fail()`

**5.12. Diff View + Merge UI**  
- `MergeDialog(original, generated)` → show before/after diff (difflib.HtmlDiff)
- Options: Replace, Append, Selective merge
- **Tests:** `test_replace()`, `test_append()`, `test_diff_highlights()`

---

## 6. Example Artifacts

### 6.1. Improved System Prompt (v2)

```markdown
# templates/system_prompt_v2.txt
# version: 2.0
# description: Fantasy world-builder with structured output guidance

You are an expert fantasy world-builder. Tone: descriptive, evocative.

**TIME:** 1.0 = 1 day (0.5 = noon). Use for dates/durations.

**OUTPUT FORMAT:**
```json
{
  "name": "Entity Name",
  "type": "Character|Location|Faction|Item|Concept",
  "description": "100-300 word description",
  "attributes": {"key": "value"}
}
```

**GUIDELINES:**
- Be concise (100-300 words)
- Maintain consistency with RAG context
- Avoid contradictions
- Use sensory details
- Consider timeline logic
```

### 6.2. Few-Shot Entity Examples

```json
// Example 1 - Wizard
User: Create a wise old wizard.
Assistant: {
  "name": "Aldric the Wise",
  "type": "Character",
  "description": "An ancient wizard with silver beard...",
  "attributes": {"age": 300, "alignment": "good"}
}

// Example 2 - Haunted Forest
User: Describe a haunted forest.
Assistant: {
  "name": "The Whispering Woods",
  "type": "Location",
  "description": "Ancient trees twist into grotesque shapes...",
  "attributes": {"danger_level": "high", "inhabitants": ["wraiths"]}
}
```

### 6.3. JSON Schemas

```python
ENTITY_SCHEMA = {
    "type": "object",
    "required": ["name", "type", "description"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "type": {"type": "string", "enum": ["Character", "Location", "Faction", "Item", "Concept"]},
        "description": {"type": "string", "minLength": 50, "maxLength": 2000},
        "attributes": {"type": "object"}
    }
}
```

### 6.4. RAG Condensation Pseudo-Code

```python
def condense_rag_chunks(provider, chunks, max_tokens_per_chunk=100):
    """
    Before: 3 × 2000 chars = 6000 chars
    After: 3 × 100 tokens = ~400 chars
    """
    condensed = []
    for chunk in chunks:
        summary_prompt = f"Summarize in {max_tokens_per_chunk} tokens:\n{chunk['description'][:1000]}\nSummary:"
        result = provider.generate(summary_prompt, max_tokens=max_tokens_per_chunk, temperature=0.3)
        condensed.append(f"**{chunk['name']}**: {result['text']}")
    return "\n".join(condensed)
```

### 6.5. Consistency Check Rules

```python
class ConsistencyChecker:
    def check_birth_death_order(self, entity):
        birth = entity.attributes.get("birth_date")
        death = entity.attributes.get("death_date")
        if birth and death and birth >= death:
            return Warning(f"{entity.name} born after death")
    
    def check_circular_relations(self, entity_id):
        visited = set()
        stack = [entity_id]
        while stack:
            current = stack.pop()
            if current in visited:
                return Warning(f"Circular relation: {current}")
            visited.add(current)
            relations = self.db.get_relations(current, rel_type="parent_of")
            stack.extend(r["target_id"] for r in relations)
```

---

## 7. Recommended Next-Code PRs

| PR # | Title | Est. Time | Risk | Impact |
|------|-------|-----------|------|--------|
| 1 | Prompt template loader + versioning | 2-4 hours | Low | Med |
| 2 | Few-shot examples (entity/location) | 2-3 hours | Low | High |
| 3 | JSON schema validation wrapper | 4-6 hours | Low | High |
| 4 | Provenance metadata in RAG | 1 day | Low | Med |
| 5 | RAG condensation pipeline | 2-3 days | Med | High |
| 6 | Structured output enforcement | 2-3 days | Med | High |
| 7 | Entity registry + deduplication | 4-5 days | High | High |
| 8 | Consistency checker | 3-4 days | Med | High |
| 9 | CI LLM output tests | 1-2 days | Low | Med |
| 10 | Telemetry/metrics | 2-3 days | Low | Med |
| 11 | Multi-provider fallback | 2-3 days | Med | Med |
| 12 | Diff view + merge UI | 5-7 days | Med | High |

**Order:** Start with **PR1-3** (quick wins), then **PR5-6** (core), finally **PR7-8** (complex).

---

## 8. Why This Matters for Worldbuilding

### Maintain Canonical Lore
**Fix:** Fuzzy-match deduplication prevents "Gandalf the Grey" + "Gandalf the Gray"  
**Benefit:** Single source of truth, consistent relationships

### Reduce Hallucination/Contradictions
**Fix:** Consistency checker enforces birth < death, event A caused B ⇒ A.date ≤ B.date  
**Benefit:** Internally consistent world, no temporal paradoxes

### Enable Reliable Machine-Readable Outputs
**Fix:** Structured JSON with schema validation  
**Benefit:** Automated workflows (bulk import, CSV export, API integration)

### Improve User Trust
**Fix:** Provenance shows "Sources: Entity A, B", diff view before accepting  
**Benefit:** Users verify sources, selectively merge content

### Allow Safe Offline/Local-First
**Fix:** Multi-provider fallback (LM Studio → OpenAI → Anthropic)  
**Benefit:** Works offline, graceful degradation, private data stays local

### Ensure Provenance & Auditability
**Fix:** Track AI-generated vs human-written, secure audit logs with redaction  
**Benefit:** Compliance, content origin tracking, safe audit trails

---

## 9. UI/UX Notes for Entity Editor LLM Panel

### Structured Preview
```
┌────────────────────────────────────┐
│ Generated Content Preview          │
├────────────────────────────────────┤
│ {                                  │
│   "name": "Aldric",                │
│   "type": "Character",             │
│   "attributes": { ▼ }              │  ← Collapsible
│ }                                  │
├────────────────────────────────────┤
│ ✓ Valid JSON   ⚠ Schema OK        │
└────────────────────────────────────┘
```

### Provenance List
```
Sources (RAG Context):
  • Gandalf (Character) - 0.92  [View]
  • The Shire (Location) - 0.87  [View]
```

### Duplicate Warning
```
⚠ Similar Entity: "Gandalf the Wise" (90% match)
  ○ Merge with existing
  ○ Create as new
  [ View Existing ]  [ Cancel ]  [ Proceed ]
```

### Accept/Reject/Merge Buttons
```
[ Reject ]  [ Merge... ]  [ Accept ]
```

### Diff View
```
┌────────────────┬────────────────────┐
│ Current        │ Generated          │
├────────────────┼────────────────────┤
│ Gandalf is a   │ Gandalf is a wise  │  ← Added (green)
│ wizard.        │ and ancient wizard.│
└────────────────┴────────────────────┘
Merge Options:
  ○ Replace entire   ○ Append   ○ Selective
                 [ Cancel ]  [ Apply ]
```

---

## 10. Checklist (Acceptance Criteria)

**Infrastructure:**
- [ ] Prompt templates in `templates/` directory
- [ ] `PromptLoader` with version management
- [ ] 3+ few-shot examples (entity, location, event)
- [ ] JSON schemas defined (Entity, Location, Event)

**Core Features:**
- [ ] RAG condensation with summarization
- [ ] Structured output enforcement (function-calling or retry)
- [ ] Entity registry with fuzzy matching (80%+)
- [ ] Consistency checker (timeline/relation rules)

**UI/UX:**
- [ ] Provenance metadata displayed ("Sources: ...")
- [ ] Duplicate warnings shown
- [ ] Diff view for before/after
- [ ] Accept/Reject/Merge buttons

**Testing:**
- [ ] CI tests for LLM output validation
- [ ] Regression prompts with schema assertions
- [ ] Telemetry opt-in implemented
- [ ] Integration tests for RAG and structured output

**Documentation:**
- [ ] Updated docs (prompt templates, few-shot)
- [ ] User guide for AI workflows
- [ ] Security guidelines (audit logs, redaction)
- [ ] Migration guide for structured outputs

---

## 11. Security & Privacy

### Audit Log Security
- Implement opt-in redaction (strip custom attributes)
- Add retention policy (auto-delete >30 days)
- Encrypt logs at rest (OS keychain)

### API Key Storage
- Use OS credential manager (Windows Credential Manager, macOS Keychain)
- Never log API keys

### Cloud Provider Data Leakage
- Warn users when enabling cloud providers
- Add "Data Privacy Mode": disable RAG for cloud

---

## 12. Performance Notes

### RAG Condensation
- **Bottleneck:** 3 separate LLM calls for summarization
- **Optimization:** Batch into single prompt: "Summarize these 3 entries..."
- **Trade-off:** Reduces API calls (3→1) but increases single-call latency

### Structured Output Retries
- **Cost:** Each retry = additional LLM call
- **Optimization:** Exponential backoff, increase temp on retry
- **Max retries:** 2-3 attempts

### Entity Registry
- **Bottleneck:** O(N) fuzzy matching for N entities
- **Optimization:** Trigram index or BK-tree for sub-linear search (>1000 entities)

---

## 13. Future Enhancements

- Chunk embeddings for long descriptions
- Cross-modal RAG (image captions, map labels)
- Relation-aware search ("Who caused X?")
- Prompt optimizer (A/B testing, auto-tune)
- Voice input (speech-to-text for accessibility)
- Collaborative filtering suggestions

---

## Conclusion

ProjektKraken's LLM integration is **architecturally sound** with strong abstractions and local-first principles. The **critical gaps**—structured outputs, RAG condensation, entity deduplication, consistency checks—are **well-scoped and implementable in 1-2 months**. Prioritizing Quick Wins (PR1-4) delivers immediate quality improvements with minimal risk. Medium-Term work (PR5-8) addresses core workflow gaps. The system is **production-ready for basic use today** and will be **best-in-class for AI-assisted worldbuilding** after implementing these recommendations.

**Next Action:** Start with **PR1** (prompt template loader) to establish infrastructure for iterative improvement.

---

**Document End**
