# Architecture Changes Diagram

## Before Refactoring - Tight Coupling

```mermaid
graph TD
    subgraph "Service Layer"
        DH[DataHandler]
        DB[(DatabaseService)]
    end
    
    subgraph "UI Layer"
        MW[MainWindow]
        UL[UnifiedList]
        TL[Timeline]
        EE[EventEditor]
        UI[UIManager]
        TV[TimelineView]
        GBM[GroupBandManager]
    end
    
    DH -->|direct access| UL
    DH -->|direct access| TL
    DH -->|direct access| EE
    DH -->|direct access| MW
    
    TV -->|direct access| DB
    GBM -->|direct access| DB
    
    UI -->|implicit interface| MW
    
    style DH fill:#ff6b6b
    style TV fill:#ff6b6b
    style GBM fill:#ff6b6b
    style UI fill:#ffd93d
```

**Problems:**
- ❌ DataHandler directly manipulates MainWindow widgets
- ❌ Timeline UI layer directly accesses DatabaseService (layer violation)
- ❌ UIManager assumes methods exist on MainWindow (implicit interface)
- ❌ Violates Law of Demeter
- ❌ Tight coupling makes testing difficult

## After Refactoring - Loose Coupling

```mermaid
graph TD
    subgraph "Service Layer"
        DH[DataHandler]
        DB[(DatabaseService)]
    end
    
    subgraph "Controller Layer"
        MW[MainWindow<br/>implements:<br/>- TimelineDataProvider<br/>- MainWindowProtocol]
        CM[ConnectionManager]
    end
    
    subgraph "UI Layer"
        UL[UnifiedList]
        TL[Timeline]
        EE[EventEditor]
        UI[UIManager]
        TV[TimelineView]
        GBM[GroupBandManager]
    end
    
    subgraph "Interfaces"
        TDP[TimelineDataProvider<br/>Protocol]
        MWP[MainWindowProtocol]
    end
    
    DH -->|emits signals| CM
    CM -->|connects to| MW
    MW -->|updates| UL
    MW -->|updates| TL
    MW -->|updates| EE
    
    MW -.implements.-> TDP
    MW -.implements.-> MWP
    
    TV -->|uses callbacks| MW
    GBM -->|uses callbacks| MW
    MW -->|queries| DB
    
    UI -->|typed with| MWP
    UI -->|calls methods on| MW
    
    style DH fill:#51cf66
    style MW fill:#51cf66
    style TV fill:#51cf66
    style GBM fill:#51cf66
    style UI fill:#51cf66
    style TDP fill:#a9e34b
    style MWP fill:#a9e34b
```

**Solutions:**
- ✅ DataHandler emits signals instead of direct access
- ✅ MainWindow acts as mediator between Timeline and Database
- ✅ GroupBandManager uses callbacks (no direct DB access)
- ✅ UIManager uses Protocol type hint (explicit interface)
- ✅ Proper layer separation enforced
- ✅ Components are loosely coupled and testable

## Signal Flow - Data Updates

```mermaid
sequenceDiagram
    participant Worker
    participant DataHandler
    participant ConnectionManager
    participant MainWindow
    participant UI as UI Widgets
    
    Worker->>DataHandler: on_events_loaded(events)
    DataHandler->>DataHandler: Cache events internally
    DataHandler->>ConnectionManager: emit events_ready(events)
    ConnectionManager->>MainWindow: _on_events_ready(events)
    MainWindow->>MainWindow: Update cache
    MainWindow->>UI: unified_list.set_data()
    MainWindow->>UI: timeline.set_events()
    
    DataHandler->>ConnectionManager: emit status_message("Loaded...")
    ConnectionManager->>MainWindow: status_bar.showMessage()
    
    DataHandler->>ConnectionManager: emit suggestions_update_requested(items)
    ConnectionManager->>MainWindow: _on_suggestions_update(items)
    MainWindow->>UI: event_editor.update_suggestions()
    MainWindow->>UI: entity_editor.update_suggestions()
```

## Data Provider Pattern - Timeline

```mermaid
sequenceDiagram
    participant MainWindow
    participant TimelineView
    participant GroupBandManager
    participant DB as DatabaseService
    
    Note over MainWindow: Initialization
    MainWindow->>TimelineView: set_data_provider(self)
    TimelineView->>GroupBandManager: new GroupBandManager(callbacks)
    
    Note over GroupBandManager: User requests grouping
    GroupBandManager->>GroupBandManager: call get_group_metadata(tags)
    GroupBandManager->>MainWindow: callback: get_group_metadata(tags)
    MainWindow->>DB: get_group_metadata(tags)
    DB-->>MainWindow: metadata
    MainWindow-->>GroupBandManager: metadata
    GroupBandManager->>GroupBandManager: Create bands
    
    GroupBandManager->>GroupBandManager: call get_events_for_group(tag)
    GroupBandManager->>MainWindow: callback: get_events_for_group(tag)
    MainWindow->>DB: get_events_for_group(tag)
    DB-->>MainWindow: events
    MainWindow-->>GroupBandManager: events
```

## Key Design Patterns

### 1. Observer Pattern (Signals/Slots)
```mermaid
graph LR
    Subject[DataHandler<br/>Subject] -->|emits| Signal[Qt Signal]
    Signal -->|notifies| Observer1[MainWindow<br/>Observer 1]
    Signal -->|notifies| Observer2[Other Components<br/>Observer 2]
    
    style Subject fill:#4dabf7
    style Signal fill:#ffd43b
    style Observer1 fill:#51cf66
    style Observer2 fill:#51cf66
```

### 2. Callback Pattern
```mermaid
graph LR
    UI[GroupBandManager<br/>UI Component] -->|callback| Mediator[MainWindow<br/>Mediator]
    Mediator -->|query| Service[DatabaseService<br/>Data Layer]
    Service -->|return data| Mediator
    Mediator -->|return data| UI
    
    style UI fill:#ff6b6b
    style Mediator fill:#51cf66
    style Service fill:#4dabf7
```

### 3. Protocol Pattern (Structural Typing)
```mermaid
graph TD
    Protocol[Protocol Interface<br/>MainWindowProtocol] -.defines.-> Methods[Required Methods:<br/>- _on_configure_grouping<br/>- _on_clear_grouping<br/>+ attributes]
    
    Implementer[MainWindow] -.implements.-> Protocol
    Consumer[UIManager] -->|typed with| Protocol
    Consumer -->|uses| Implementer
    
    style Protocol fill:#a9e34b
    style Implementer fill:#51cf66
    style Consumer fill:#4dabf7
```

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Coupling** | Tight (direct references) | Loose (signals & callbacks) |
| **Testability** | Hard (needs full UI) | Easy (isolated components) |
| **Layer Separation** | Violated | Enforced |
| **Interface Clarity** | Implicit | Explicit (Protocols) |
| **Maintainability** | Brittle | Flexible |
| **Type Safety** | Weak | Strong (typed protocols) |
