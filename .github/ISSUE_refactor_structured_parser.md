# refactor: extract structured text parser utility for LLM response handling

## Problem

Multiple analyzers in IntelligenceAnalyzer manually parse structured LLM responses using similar patterns:

1. Split by delimiter (EVENT:, ISSUE:, etc.)
2. Extract prefixed fields (DATE:, DESCRIPTION:, SEVERITY:)
3. Validate and create domain objects

**Current locations:**
- src/services/intelligence_analyzer.py:_parse_lore_suggestions() (lines 635-650)
- src/services/intelligence_analyzer.py:_parse_plot_holes_response() (implicit)
- src/services/intelligence_analyzer.py:_parse_relation_proposals_response() (implicit)

Each uses hard-coded prefix matching and manual string slicing.

## Solution

Create a reusable StructuredTextExtractor at src/services/structured_parser.py:

```python
class StructuredTextExtractor:
    """Extract structured fields from delimited text blocks."""
    
    @staticmethod
    def extract_blocks(text: str, delimiter: str) -> list[str]:
        """Split text into non-empty blocks by delimiter."""
        parts = text.split(delimiter)
        return [part.strip() for part in parts[1:] if part.strip()]
    
    @staticmethod
    def extract_fields(
        block: str, 
        field_prefixes: dict[str, str]
    ) -> dict[str, str]:
        """Extract field values from a block using prefix matching.
        
        Args:
            block: Text block to parse.
            field_prefixes: {field_name: prefix} e.g. {"date": "DATE:", "desc": "DESCRIPTION:"}
        
        Returns:
            Dict mapping field_name to value (empty string if not found).
            Special key "_primary" contains first line (event name, etc).
        """
```

## Refactoring
Update intelligence_analyzer.py to use the extractor:

**Before:**
```python
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
name = lines[0] if lines else ""
date_str = ""
description = ""
for line in lines[1:]:
    if line.startswith("DATE:"):
        date_str = line.replace("DATE:", "", 1).strip()
    elif line.startswith("DESCRIPTION:"):
        description = line.replace("DESCRIPTION:", "", 1).strip()
```

**After:**
```python
fields = StructuredTextExtractor.extract_fields(
    block,
    {"date_str": "DATE:", "description": "DESCRIPTION:"}
)
name = fields["_primary"]
date_str = fields["date_str"]
description = fields["description"]
```

## Benefits
- Consolidates parsing logic
- Reduces per-analysis boilerplate
- Easier to test and validate
- Flexible for new LLM response formats

## Priority
Low - refactoring for maintainability, not blocking any features
