# Migration Plan: Legacy Endpoints → SessionEngine Architecture

## Overview

This document outlines the migration plan from the current ad-hoc endpoint architecture to the new unified SessionEngine approach. The migration ensures backward compatibility while providing a clear path forward.

## Current State Analysis

### Existing Endpoints (Legacy)

#### WebSocket Detection
- **`/realtime/ws/detection/{client_id}`** - Basic WebSocket with frame processing
- **Issues**: Inconsistent state management, no session persistence, manual model loading per connection

#### Session Management (Multiple Systems)
- **`/session/init`** - Creates autocorrector sessions only
- **`/autocorrector/session/create`** - Duplicate session creation
- **`/phrase/finalize`** - Manual phrase completion with timer service
- **Issues**: Multiple overlapping session systems, inconsistent state

#### Detection Endpoints
- **`/detection/continuous-detect`** - Frame processing with timer management  
- **`/realtime/continuous-detect`** - Alternate detection endpoint
- **Issues**: Duplicate logic, separate model instances, inconsistent timing

#### Word/Phrase Management
- **`/autocorrector/letter/add`** - Manual letter addition
- **`/autocorrector/word/finish`** - Word completion
- **`/word-builder/*`** - Additional word building endpoints
- **Issues**: Fragmented state, no unified flow

## New SessionEngine Architecture

### Core Components

1. **`SessionEngine`** - Unified per-session state machine
2. **`SessionManager`** - Global registry with shared resources
3. **`/realtime/ws/detection/{session_id}`** - Primary WebSocket endpoint
4. **`/session/*`** - Unified session management REST API

### Key Improvements

✅ **Single Source of Truth**: All detection, timing, and state logic in SessionEngine  
✅ **Shared Resources**: ML models loaded once, shared across all sessions  
✅ **Consistent Timing**: Exact `main.py` timing logic replicated  
✅ **Stateful Sessions**: Persistent sessions with automatic cleanup  
✅ **Real-time Updates**: Complete state updates over WebSocket  
✅ **Clean API**: Minimal REST endpoints for configuration  

## Migration Strategy

### Phase 1: Parallel Deployment (✅ Complete)

**Status**: Both architectures running simultaneously

**Legacy Endpoints**: 
- Marked as deprecated with warning tags
- Continue to function for existing clients
- No new features added

**SessionEngine Endpoints**:
- Available at new paths (`/realtime/ws/detection/{session_id}`)
- Full functionality for new clients
- Production ready

### Phase 2: Client Migration (In Progress)

**Frontend Migration Checklist**:

- [ ] **WebSocket Connection**
  ```javascript
  // OLD
  ws://server/realtime/ws/detection/{client_id}
  
  // NEW  
  ws://server/realtime/ws/detection/{session_id}
  ```

- [ ] **Session Initialization**
  ```javascript
  // OLD: Multiple calls required
  POST /autocorrector/session/create
  POST /session/init
  
  // NEW: Single call
  POST /session/init
  ```

- [ ] **Frame Processing**
  ```javascript
  // OLD: Raw base64 string
  websocket.send(frameBase64);
  
  // NEW: Structured JSON
  websocket.send(JSON.stringify({
    type: "frame",
    frameBase64: frameBase64
  }));
  ```

- [ ] **Control Messages**
  ```javascript
  // OLD: Separate REST calls
  POST /phrase/finalize
  POST /detection/reset
  
  // NEW: WebSocket control messages
  websocket.send(JSON.stringify({
    type: "control",
    action: "clear_all"
  }));
  ```

- [ ] **State Updates**
  ```javascript
  // OLD: Basic predictions only
  {
    "predictions": [...],
    "processing_time_ms": 23
  }
  
  // NEW: Complete state payload
  {
    "type": "state_update",
    "detection": {...},
    "word": {...},
    "sentence": {...},
    "translation": {...},
    "timers": {...},
    "tts": {...}
  }
  ```

### Phase 3: Legacy Deprecation (Planned)

**Timeline**: 4-6 weeks after Phase 2 completion

**Actions**:
- Add deprecation warnings to legacy endpoints
- Update documentation to point to SessionEngine
- Log usage metrics for legacy endpoints
- Communicate deprecation timeline to clients

**Example Deprecation Response**:
```json
{
  "status": "deprecated",
  "message": "This endpoint will be removed in v4.0. Please migrate to SessionEngine architecture.",
  "migration_guide": "https://docs.bridge.com/sessionengine-migration",
  "data": {...}
}
```

### Phase 4: Legacy Removal (Future)

**Conditions for Removal**:
- Zero legacy endpoint usage for 2+ weeks
- All known clients migrated
- SessionEngine proven stable in production

**Endpoints to Remove**:
- `/realtime/ws/detection/{client_id}` (legacy WebSocket)
- `/detection/continuous-detect`
- `/phrase/finalize` (legacy)
- `/autocorrector/letter/add`
- `/word-builder/*`
- Duplicate session endpoints

## Migration Testing

### Test Legacy → SessionEngine Equivalence

**Frame Processing Test**:
```python
# Send same frame to both endpoints
legacy_response = await call_legacy_detection(frame)
session_response = await call_session_engine(frame)

# Verify equivalent detection results
assert legacy_response["letter"] == session_response["detection"]["letter"]
assert abs(legacy_response["confidence"] - session_response["detection"]["confidence"]) < 0.01
```

**Timing Test**:
```python
# Verify timeout behavior matches main.py
await send_letters(["H", "O", "L", "A"])
await wait(4100)  # word_pause_ms + buffer
state = await get_session_state()

assert state["word"]["just_finished"] == True
assert "hola" in state["sentence"]["current"]
```

**State Consistency Test**:
```python
# Verify state updates are consistent
states = []
for frame in test_frames:
    state = await process_frame(frame)
    states.append(state)

# Verify monotonic progression
assert all(s["timestamp"] >= states[i-1]["timestamp"] for i, s in enumerate(states[1:]))
```

## Monitoring and Rollback

### Monitoring Metrics

1. **Performance Comparison**
   - Legacy vs SessionEngine processing times
   - Memory usage per session
   - WebSocket connection stability

2. **Feature Parity**
   - Detection accuracy comparison
   - Timing behavior verification  
   - Translation/TTS success rates

3. **Usage Tracking**
   - Legacy endpoint usage declining
   - SessionEngine adoption increasing
   - Error rates and patterns

### Rollback Plan

**Conditions for Rollback**:
- SessionEngine performance significantly worse than legacy
- Critical bugs affecting production users
- Frontend migration blocked by architecture issues

**Rollback Procedure**:
1. Redirect traffic back to legacy endpoints
2. Disable SessionEngine endpoints  
3. Investigate and fix issues
4. Re-enable with fixes

## Documentation Updates

### API Documentation
- [ ] Update OpenAPI specs for new endpoints
- [ ] Add SessionEngine architecture diagrams
- [ ] Create migration examples for each client type

### Developer Guide
- [ ] SessionEngine integration tutorial
- [ ] WebSocket protocol specification
- [ ] State payload reference
- [ ] Error handling best practices

### Deployment Guide  
- [ ] Production deployment checklist
- [ ] Monitoring setup instructions
- [ ] Scaling considerations
- [ ] Troubleshooting guide

## Success Criteria

### Technical Metrics
- **Performance**: SessionEngine ≤ 10% slower than legacy
- **Reliability**: >99.9% uptime for WebSocket connections
- **Memory**: ≤50% memory usage increase for shared models
- **Latency**: Frame processing <100ms average

### Business Metrics
- **Adoption**: 100% of active clients migrated
- **Stability**: Zero critical bugs for 2+ weeks
- **Maintenance**: Reduced endpoint count by >60%
- **Development**: New features only need SessionEngine implementation

## Timeline Summary

| Phase | Duration | Status | Key Deliverables |
|-------|----------|--------|-----------------|
| Phase 1: Parallel Deployment | 1 week | ✅ Complete | SessionEngine architecture deployed |
| Phase 2: Client Migration | 4-6 weeks | 🔄 In Progress | All clients using SessionEngine |
| Phase 3: Legacy Deprecation | 2 weeks | ⏳ Planned | Deprecation warnings, metrics |
| Phase 4: Legacy Removal | 1 week | ⏳ Future | Clean codebase, single architecture |

**Total Migration Timeline**: 8-10 weeks

## Risk Mitigation

### Technical Risks
- **Risk**: SessionEngine performance issues
- **Mitigation**: Extensive load testing, rollback plan

### Business Risks  
- **Risk**: Client migration delays
- **Mitigation**: Comprehensive documentation, migration support

### Operational Risks
- **Risk**: Production stability during transition
- **Mitigation**: Gradual rollout, monitoring, rollback capability

## Next Steps

1. **Immediate** (This week)
   - [ ] Complete SessionEngine testing
   - [ ] Update API documentation
   - [ ] Begin frontend migration planning

2. **Short-term** (2-4 weeks)
   - [ ] Migrate primary client to SessionEngine
   - [ ] Performance monitoring and optimization
   - [ ] Migration guide creation

3. **Medium-term** (4-8 weeks)
   - [ ] Complete all client migrations
   - [ ] Legacy endpoint deprecation
   - [ ] Production stability validation

4. **Long-term** (8+ weeks)
   - [ ] Legacy endpoint removal
   - [ ] Architecture documentation finalization
   - [ ] Next-generation features on SessionEngine