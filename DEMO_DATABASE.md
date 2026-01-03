# Demo Database: Temporal State System

This database demonstrates the **Relation-driven Temporal State** system with Middle-earth inspired sample data.

## What's Inside

### Entities (6)
- **Characters**: Frodo Baggins, Gandalf the Grey, Aragorn
- **Locations**: The Shire, Rivendell, Gondor

### Events (4)
1. **Frodo Departs the Shire** (3018.0)
2. **Council of Elrond** (3018.8)
3. **Aragorn's Coronation** (3019.5)
4. **Return to the Shire** (3021.0)

### Temporal Relations (10)
All relations use **dynamic event-relative timing** with `valid_from_event` and `valid_to_event` flags.

## How to Use

1. **Open the Database**
   - File → Open Database
   - Select `demo.kraken`

2. **Try the Timeline**
   - Open "Frodo Baggins" in Entity Inspector
   - Move the timeline playhead between years 3018-3021
   - Watch attributes change:
     - At 3018: `status = "Ring Bearer"`, `carrying = "One Ring"`
     - At 3021: `status = "Returning Home"`, `carrying = null`

3. **Try Editing Events**
   - Open "Frodo Departs the Shire" event
   - Change the date from 3018 to 3020
   - Notice Frodo's state at T=3019 changes automatically (cache invalidation works!)

4. **Inspect Aragorn**
   - Open "Aragorn" in Entity Inspector
   - Set playhead to 3019.5 (coronation)
   - Watch `title` change to "King of Gondor"

## What This Demonstrates

✅ **Event-relative timing**: Relations track event dates dynamically  
✅ **Cache invalidation**: Moving events updates entity states  
✅ **Categorized relations**: Participants vs Locations vs Custom  
✅ **UX improvements**: Tooltips, empty states, larger buttons  

## Regenerating

To recreate the demo database:
```bash
.venv\Scripts\python.exe create_demo_db.py
```
