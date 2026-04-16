# Analysis Suite

## What This Does

The Analysis Suite is your world's health checker and AI-powered consultant. It runs three types of analysis to help you spot problems, understand your timeline, and get AI-powered suggestions for filling gaps and fixing inconsistencies in your world.

Think of it as a combination spell-checker, timeline auditor, and creative writing assistant for your worldbuilding.

## What You Can Do

### World Validation
- Find entities with no connections (orphaned characters, unused locations)
- Discover broken links and missing references
- Identify incomplete information (missing descriptions, descriptions that are too short)
- Find unused tags that clutter your world
- See how complete each entity and event is (completeness score)
- Get a health overview of your entire world

### Temporal Analysis
- Find gaps in your timeline (long periods with no events)
- Detect conflicts in character lifespans (events happening after a character dies, etc.)
- Check if relationships make temporal sense
- See when your earliest and latest events occur
- Identify which characters span the timeline gaps

### Intelligence Suite (AI-Powered)
- Get AI suggestions for missing relationships between entities
- Detect plot holes and narrative inconsistencies
- Generate lore suggestions to fill timeline gaps
- Review AI reasoning for each suggestion
- See the model's confidence level for each suggestion

## How to Use It

### Access the Analysis Suite

1. Open ProjektKraken and load your world
2. Look for the **Analysis** panel (usually on the right side of the application, in the dock)
3. You'll see three buttons at the top: **Validate World**, **Analyze Timeline**, and **Run AI Analysis**

### Run World Validation

1. Click the **Validate World** button
2. Wait for the analysis to complete (you'll see a status message)
3. The **Validation** tab will open automatically showing:
   - **Health Summary**: Overall completeness percentage, number of issues, entity and event counts
   - **Validation Issues Table**: Each problem found, with severity level (CRITICAL, WARNING, INFO), problem type, affected object name, description, and suggested fix
   - **Completeness Scores Table**: Every entity and event, ranked by how complete they are (lowest first), showing name, type, score, and tag count

**Reading the Issues Table:**
- **Severity**: CRITICAL (red) = data integrity risk; WARNING (orange) = quality issue; INFO (blue) = suggestion
- **Type**: The category of problem (orphaned entity, broken reference, incomplete description, etc.)
- **Message**: What the problem is
- **Suggestion**: How you might fix it (if available)

### Run Temporal Analysis

1. Click the **Analyze Timeline** button
2. Wait for the analysis to complete
3. The **Timeline** tab will open automatically showing:
   - **Timeline Summary**: Earliest and latest event dates, total gap duration, number of conflicts
   - **Timeline Gaps**: Periods with no events, how long they are, which characters' lifespans span them
   - **Temporal Conflicts**: Events that violate character lifespans, relation windows, or state logic
   - **Character Lifespans**: Birth and death dates for characters, violations detected, events outside the lifespan

**Understanding the Results:**
- **Gaps** don't mean your timeline is broken—they're just periods with no recorded events. Some gaps might be intentional.
- **Conflicts** flag things that seem wrong (a character attending an event 10 years after they died, for example)
- **Lifespans** show computed birth and death dates based on events involving that character

### Run AI Analysis

1. Click the **Run AI Analysis** button
2. Wait for the AI to analyze your world (this may take longer than validation)
3. The **Intelligence** tab will open automatically showing:
   - **Plot Holes**: Detected inconsistencies and narrative problems, with severity and suggested resolution
   - **Relation Proposals**: Entities that might have relationships, with reasoning and confidence scores
   - **Lore Suggestions**: AI-generated event descriptions to fill timeline gaps
   - **Audit Log**: Raw LLM interactions (for transparency and debugging)

**Interpreting AI Results:**
- **Confidence Score** (0.0–1.0): Higher = the AI is more certain. Use it as a guide, not gospel.
- **Suggested Resolution**: The AI's proposed fix for plot holes
- **Reasoning**: Why the AI thinks there's a missing relationship or problem

## Common Workflows

### Clean Up Your World

1. Run **Validate World**
2. Scan the Issues table for CRITICAL items (red) first
3. For each critical issue:
   - Click on the affected object to navigate to it in the editor
   - Make the fix (add missing description, delete broken reference, reconnect the entity)
4. Run validation again to see if you've resolved the issues
5. Repeat until you have fewer critical issues

### Fill Timeline Gaps

1. Run **Analyze Timeline**
2. Look at the Timeline Gaps section
3. Decide if each gap needs events
4. For gaps you want to fill:
   - Use the **Intelligence Suite** to get AI-generated lore suggestions
   - Create new events based on the suggestions, or
   - Manually add events during the gap period
5. Re-run timeline analysis to see the updated timeline

### Discover Missing Relationships

1. Run **AI Analysis**
2. Look at the Relation Proposals section
3. Review each suggestion with its reasoning
4. For proposals you agree with:
   - Navigate to the source entity in the editor
   - Create the relationship manually, or
   - Use Fast Inject (if available) to add relationships from the panel
5. For proposals you disagree with, ignore them—the AI isn't always right

### Track Completeness Progress

1. Run **Validate World** regularly (e.g., weekly while building your world)
2. Check the completeness scores to see which entities need more detail
3. Sort the Completeness table by score (lowest first) to see what needs work
4. Add descriptions, tags, images, and relationships to improve scores
5. Re-run validation to watch your world health percentage grow

## Tips & Gotchas

### Timeline Gaps
- Not all gaps are problems. If your world has long peaceful periods or historical dark ages, gaps are realistic.
- The Analysis Suite just *identifies* gaps; it's up to you to decide if they need filling.

### Temporal Conflicts
- Some conflicts might be edge cases the AI gets wrong (e.g., a character can attend an event on the exact day of death).
- Review each conflict and decide if it's actually a problem or a misunderstanding.

### Completeness Score
- A 100% complete entity is rare and not required. Even 60% is solid.
- Focus on CRITICAL validation issues first; minor completeness improvements can come later.
- The score rewards:
  - **Descriptions** (longest bang for buck): 40 points for 50+ characters, 20 for any description
  - **Tags**: 5 points each, capped at 20
  - **Relations**: 5 points each, capped at 20
  - **Images**: 10 points

### AI Analysis
- The AI is helpful but not infallible. Use confidence scores as a guide.
- AI suggestions improve as your descriptions get more detailed.
- If you've just added a lot of new content, re-run analysis to get fresh suggestions.

### Analysis Results Don't Auto-Update
- The Analysis Suite runs on demand—your reports are snapshots in time.
- If you fix issues and want to check progress, you need to run the analysis again.
- There's no "watch mode" yet; plan to run analysis periodically.

### Broken References
- If you delete an entity that other entities reference, the Validation report will flag broken references.
- Fix them by removing the broken relationships or re-linking to a different entity.

## Connecting the Pieces

The Analysis Suite works best with your other tools:

- **Entity Inspector**: Use it to fix the specific issues the suite finds
- **Timeline View**: Use it to see the gaps and conflicts the Temporal Analysis identifies
- **Relation Graph**: After running AI Analysis, the graph helps you visualize the new relationships
- **Search**: Find specific entities flagged in analysis reports quickly
- **Tags**: Use them to organize entities and improve completeness scores
