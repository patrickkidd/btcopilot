# Audio Upload Flow Documentation

## Overview

The audio upload system enables auditors to upload audio recordings of clinical discussions, automatically transcribe them using AssemblyAI, and extract structured clinical data through AI-powered analysis. The flow involves client-side upload, third-party transcription, backend processing, and asynchronous data extraction.

**Key Features:**
- Direct client-to-AssemblyAI upload (no server intermediary)
- Automatic speaker diarization
- Sequential AI extraction of clinical data from statements
- Real-time progress tracking
- Association with user diagrams

## Architecture Components

### Frontend
- **Audio Upload Client**: [btcopilot/training/static/js/audio-upload-client.js](../training/static/js/audio-upload-client.js)
- **Progress Tracker**: [btcopilot/training/static/js/extraction-progress.js](../training/static/js/extraction-progress.js)
- **UI Template**: [btcopilot/training/templates/partials/user_diagrams.html](../training/templates/partials/user_diagrams.html)

### Backend API
- **Discussion Routes**: [btcopilot/training/routes/discussions.py](../training/routes/discussions.py)
- **Celery Tasks**: [btcopilot/training/tasks.py](../training/tasks.py)
- **Celery Config**: [btcopilot/celery.py](../celery.py)

### Database Models
- **Discussion**: [btcopilot/personal/models/discussion.py](../personal/models/discussion.py)
- **Statement**: [btcopilot/personal/models/statement.py](../personal/models/statement.py)
- **Speaker**: [btcopilot/personal/models/speaker.py](../personal/models/speaker.py)

### External Services
- **AssemblyAI**: Third-party transcription service with speaker diarization

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER ACTION                                                      │
│    - Drag & drop audio file onto diagram card                       │
│    - Or click to select file                                        │
│    Supported: MP3, WAV, M4A, MP4, FLAC, OGG, WEBM, AAC            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. CLIENT-SIDE VALIDATION (audio-upload-client.js:13-31)          │
│    - Check MIME type and file extension                            │
│    - Display upload progress UI                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. FETCH UPLOAD TOKEN                                               │
│    GET /training/discussions/upload_token                           │
│    Returns: AssemblyAI API key                                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. DIRECT UPLOAD TO ASSEMBLYAI (audio-upload-client.js:33-50)     │
│    POST https://api.assemblyai.com/v2/upload                       │
│    Returns: upload_url                                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. REQUEST TRANSCRIPTION (audio-upload-client.js:51-75)           │
│    POST https://api.assemblyai.com/v2/transcript                   │
│    Body: { audio_url, speaker_labels: true }                       │
│    Returns: transcript_id                                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. POLL FOR COMPLETION (audio-upload-client.js:78-99)             │
│    GET https://api.assemblyai.com/v2/transcript/{id}               │
│    Poll every 3 seconds until status === "completed"                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. SEND TO BACKEND (audio-upload-client.js:196-218)               │
│    POST /training/discussions/transcript?diagram_id=X&title=Y      │
│    Body: Full AssemblyAI transcript JSON                            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. BACKEND PROCESSING (discussions.py:218-347)                     │
│    - Validate user role (AUDITOR required)                          │
│    - Determine target diagram                                       │
│    - Create Discussion record                                       │
│    - Create Speaker records (from diarization)                      │
│    - Create Statement records (one per utterance)                   │
│    - Commit to database                                             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. INITIALIZE PROGRESS TRACKER (extraction-progress.js:12-29)     │
│    - Display progress bar UI                                        │
│    - Begin polling for extraction status                            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 10. ADMIN TRIGGERS EXTRACTION (manual step)                         │
│     Celery task: extract_discussion_statements                      │
│     Sets discussion.extracting = True                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 11. ASYNC STATEMENT PROCESSING (tasks.py:20-46)                    │
│     Celery task: extract_next_statement                             │
│     ┌─────────────────────────────────────────┐                    │
│     │ For each statement:                     │                    │
│     │ 1. Load diagram data                    │                    │
│     │ 2. Run AI extraction (GPT-4o-mini)      │                    │
│     │ 3. Store pdp_deltas JSON                │                    │
│     │ 4. Self-schedule next statement         │                    │
│     └─────────────────────────────────────────┘                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 12. PROGRESS POLLING (extraction-progress.js:110-122)              │
│     GET /training/discussions/{id}/progress every 2 seconds         │
│     Returns: {total, processed, pending, percent_complete}          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 13. COMPLETION                                                      │
│     - Progress bar shows 100%                                       │
│     - UI fades out progress indicator                               │
│     - User can review in audit interface                            │
└─────────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### GET /training/discussions/upload_token
**Purpose**: Retrieve AssemblyAI API key for client-side upload

**Auth**: Requires `ROLE_AUDITOR`

**Response**:
```json
{
  "success": true,
  "api_key": "assemblyai_api_key_here"
}
```

**Location**: [discussions.py:646-658](../training/routes/discussions.py#L646-L658)

---

### POST /training/discussions/transcript
**Purpose**: Create Discussion from AssemblyAI transcript data

**Auth**: Requires `ROLE_AUDITOR`

**Query Parameters**:
- `diagram_id` (optional): Target diagram ID. If omitted, uses user's free diagram
- `title` (optional): Discussion title/summary

**Request Body**: Full AssemblyAI transcript JSON containing:
```json
{
  "utterances": [
    {
      "speaker": "A",
      "text": "Utterance text here",
      "start": 1000,
      "end": 5000,
      "confidence": 0.95,
      "words": [...]
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "discussion_id": 123,
  "message": "Discussion created from transcript",
  "redirect": "/training/discussions/123"
}
```

**Processing Logic** ([discussions.py:218-347](../training/routes/discussions.py#L218-L347)):
1. Validate user has AUDITOR role
2. Determine target diagram (create free diagram if needed)
3. Create Discussion record with summary
4. Map speaker labels to Speaker records
5. Create Statement records with order field for sorting
6. Commit transaction
7. Return discussion_id for progress tracking

---

### GET /training/discussions/<int:id>/progress
**Purpose**: Poll extraction progress for real-time updates

**Auth**: Requires authenticated user

**Response**:
```json
{
  "total": 150,
  "processed": 75,
  "pending": 75,
  "is_processing": true,
  "extracting": true,
  "percent_complete": 50
}
```

**Location**: [discussions.py:998-1067](../training/routes/discussions.py#L998-L1067)

## Database Schema

### Discussion
**Table**: `discussions`

**Fields**:
- `id`: Primary key
- `user_id`: Foreign key to User (owner/auditor)
- `diagram_id`: Foreign key to Diagram (clinical diagram context)
- `summary`: Text description/title
- `discussion_date`: Optional datetime of actual discussion
- `extracting`: Boolean flag indicating background processing active

**Relationships**:
- `statements`: One-to-many with Statement
- `speakers`: One-to-many with Speaker

**Model**: [discussion.py](../personal/models/discussion.py)

---

### Speaker
**Table**: `speakers`

**Fields**:
- `id`: Primary key
- `discussion_id`: Foreign key to Discussion
- `person_id`: References Person ID in diagram JSON (nullable)
- `name`: Speaker identifier from diarization (e.g., "A", "B", "C")
- `type`: Enum value (Expert | Subject)

**Model**: [speaker.py](../personal/models/speaker.py)

---

### Statement
**Table**: `statements`

**Fields**:
- `id`: Primary key
- `text`: The utterance text from transcription
- `discussion_id`: Foreign key to Discussion
- `speaker_id`: Foreign key to Speaker
- `pdp_deltas`: JSON field storing extracted clinical data:
  ```json
  {
    "people": [...],
    "events": [...],
    "variables": {...}
  }
  ```
- `custom_prompts`: JSON field for custom extraction prompts
- `order`: Integer for reliable chronological sorting
- `approved`: Boolean for test case generation eligibility
- `approved_by`: Username who approved statement
- `approved_at`: Timestamp of approval
- `exported_at`: Timestamp when exported as test case

**Model**: [statement.py](../personal/models/statement.py)

## AssemblyAI Integration

### Configuration
**API Key**: Retrieved from `ASSEMBLYAI_API_KEY` environment variable

**Endpoints Used**:
- **Upload**: `POST https://api.assemblyai.com/v2/upload`
- **Transcribe**: `POST https://api.assemblyai.com/v2/transcript`
- **Poll Status**: `GET https://api.assemblyai.com/v2/transcript/{transcript_id}`

### Features Enabled
- **Speaker Diarization**: `speaker_labels: true` - Automatically identifies and labels different speakers
- **Confidence Scores**: Per-word and per-utterance confidence values
- **Timestamps**: Precise start/end times for each utterance and word

### Client-Side Flow
1. **Direct Upload**: Client uploads audio directly to AssemblyAI (no server intermediary)
2. **Benefits**:
   - Reduces server bandwidth
   - Faster upload for users
   - No local storage requirements
3. **Trade-offs**:
   - API key exposed to client (scoped to upload only)
   - Audio files not persisted locally
   - Dependency on AssemblyAI CDN availability

### Supported Audio Formats
MP3, WAV, M4A, MP4, FLAC, OGG, WEBM, AAC

**Validation**: [audio-upload-client.js:13-31](../training/static/js/audio-upload-client.js#L13-L31)

## Background Processing

### Celery Task Architecture

**Broker & Backend**: Redis (configured in [celery.py](../celery.py))

### Task 1: extract_discussion_statements
**Location**: [tasks.py:49-74](../training/tasks.py#L49-L74)

**Purpose**: Initialize extraction process for a discussion

**Workflow**:
1. Load Discussion from database
2. Set `discussion.extracting = True`
3. Commit flag to database
4. Schedule first `extract_next_statement` task

**Triggered**: Manually by admin/auditor through UI

---

### Task 2: extract_next_statement
**Location**: [tasks.py:20-46](../training/tasks.py#L20-L46)

**Purpose**: Process a single statement and self-schedule for next

**Workflow** ([discussions.py:69-204](../training/routes/discussions.py#L69-L204)):

1. **Find Next Statement** (lines 42-66):
   ```python
   # Query for oldest unprocessed Subject statement
   statement = (Statement.query
                .filter_by(discussion_id=discussion_id)
                .filter(Statement.pdp_deltas == None)
                .filter(Speaker.type == SpeakerType.Subject)
                .order_by(Statement.order)
                .first())
   ```

2. **Load Diagram Data** (lines 108-111):
   - Get or create DiagramData object
   - Contains PDP (Pending Data Pool) with accumulated clinical data

3. **Run AI Extraction** (lines 118-120):
   ```python
   updated = pdp.update(
       speaker_name=speaker_name,
       statement_text=statement.text
   )
   ```
   - Uses GPT-4o-mini to extract people, events, SARF variables
   - Leverages ChromaDB vector store for semantic search
   - Employs LangChain framework for prompt management

4. **Store Results** (lines 122-145):
   ```python
   statement.pdp_deltas = json.dumps({
       "people": [...],
       "events": [...],
       "variables": {...}
   })
   ```

5. **Check Remaining** (lines 147-184):
   - Count total statements
   - Count processed statements
   - Calculate pending count

6. **Auto-Schedule Next** (lines 185-188):
   ```python
   if pending > 0:
       celery.send_task(
           'extract_next_statement',
           args=[discussion_id],
           countdown=1  # 1 second delay
       )
   ```

7. **Mark Complete** (lines 169-170):
   ```python
   if pending == 0:
       discussion.extracting = False
   ```

### Why Sequential Processing?

**Design Decision**: Process statements one at a time instead of parallel processing

**Rationale**:
- **Avoids race conditions** on shared DiagramData/PDP state
- **Maintains chronological order** of clinical data accumulation
- **Prevents database lock contention** on Statement updates
- **Simplifies error recovery** - can resume from last processed statement

**Trade-off**: Slower for long discussions, but ensures data consistency

## Error Handling

### Client-Side Errors

**File Validation** ([audio-upload-client.js:154-157](../training/static/js/audio-upload-client.js#L154-L157)):
```javascript
if (!isValidAudioFile(file)) {
    alert('Unsupported file format');
    return;
}
```

**Upload Failures** ([audio-upload-client.js:238-243](../training/static/js/audio-upload-client.js#L238-L243)):
- Display error notification with details
- Show retry button
- Clear progress UI

**Network Errors**:
- Caught in try/catch blocks
- User-friendly error messages
- Option to retry upload

### Server-Side Errors

**Authentication** ([discussions.py:220-222](../training/routes/discussions.py#L220-L222)):
```python
if not current_user.has_role('ROLE_AUDITOR'):
    return jsonify({'error': 'Unauthorized'}), 403
```

**Missing Resources** ([discussions.py:241-242](../training/routes/discussions.py#L241-L242)):
```python
if not diagram:
    return jsonify({'error': 'Diagram not found'}), 404
```

**Extraction Errors** ([discussions.py:194-204](../training/routes/discussions.py#L194-L204)):
- Log error details
- Rollback database transaction
- Return False (task not rescheduled)
- Requires manual intervention to resume

**Database Reconnection** ([discussions.py:79-82](../training/routes/discussions.py#L79-L82)):
```python
try:
    db.session.execute('SELECT 1')
except:
    db.session.rollback()
```

## Key Files Reference

### Frontend
| File | Purpose | Lines |
|------|---------|-------|
| [audio-upload-client.js](../training/static/js/audio-upload-client.js) | Audio upload, AssemblyAI integration | 220 |
| [extraction-progress.js](../training/static/js/extraction-progress.js) | Real-time progress tracking | 122 |
| [user_diagrams.html](../training/templates/partials/user_diagrams.html) | Audio drop zones UI | 97-108 |

### Backend
| File | Purpose | Key Functions |
|------|---------|---------------|
| [discussions.py](../training/routes/discussions.py) | API endpoints, transcript processing | `create_from_transcript()` (218-347), `_extract_next_statement()` (69-204) |
| [tasks.py](../training/tasks.py) | Celery task definitions | `extract_discussion_statements()`, `extract_next_statement()` |
| [celery.py](../celery.py) | Celery configuration | App factory setup |

### Models
| File | Purpose |
|------|---------|
| [discussion.py](../personal/models/discussion.py) | Discussion ORM model |
| [statement.py](../personal/models/statement.py) | Statement ORM model |
| [speaker.py](../personal/models/speaker.py) | Speaker ORM model |

## Known Limitations & Considerations

### Architecture Limitations

1. **Audio Persistence**: Audio files not stored locally - dependency on AssemblyAI CDN
   - **Impact**: Cannot replay audio if AssemblyAI deletes it
   - **Mitigation**: Consider downloading and archiving audio URLs post-transcription

2. **Sequential Processing**: Statements processed one at a time
   - **Impact**: Slow for discussions with 100+ statements
   - **Mitigation**: Could parallelize with careful locking or event sourcing

3. **No Retry Logic**: Failed extractions require manual intervention
   - **Impact**: Admin must identify and restart failed discussions
   - **Mitigation**: Add retry queue with exponential backoff

4. **Client-Side API Key**: AssemblyAI key exposed to browser
   - **Impact**: Potential misuse if user extracts key
   - **Mitigation**: Use scoped/temporary tokens if AssemblyAI supports

5. **Hard-Coded Polling**: 3-second polling on client, 2-second on progress
   - **Impact**: Unnecessary server load, delayed user feedback
   - **Mitigation**: WebSocket or Server-Sent Events for real-time updates

### Data Integrity

- **Order Field Critical**: Statement.order ensures chronological processing
- **Idempotency**: Re-running extraction overwrites existing pdp_deltas
- **Atomic Commits**: Database transactions ensure all-or-nothing creation

### Performance Characteristics

- **Upload Time**: Depends on file size and user bandwidth (direct to AssemblyAI)
- **Transcription Time**: ~30% of audio duration (AssemblyAI processing)
- **Extraction Time**: ~2-5 seconds per statement (GPT-4o-mini API call)
- **Total Time**: For 30-minute discussion (~100 statements) ≈ 9-10 minutes transcription + 3-8 minutes extraction

### Security Considerations

- **Role-Based Access**: Only AUDITOR role can upload and create discussions
- **Diagram Isolation**: Discussions scoped to user's diagrams
- **API Key Scoping**: AssemblyAI key only allows upload/transcribe, not account management
- **Input Validation**: File type checking on client (MIME type + extension)

## HIPAA Compliance & PHI Security

### ⚠️ CRITICAL: Protected Health Information (PHI) Exposure

Clinical audio recordings contain PHI under HIPAA regulations. The current architecture has **significant compliance risks** that must be addressed before production use with real patient data.

### Current Architecture Risks

#### 1. **Third-Party PHI Transmission (CRITICAL)**
**Risk**: Audio files and transcripts sent to AssemblyAI contain PHI
- Patient names, diagnoses, treatment details
- Dates of service, medical record numbers
- Other identifiable health information

**HIPAA Requirement**: Business Associate Agreement (BAA) required for any third party that handles PHI

**Current Status**: ❌ **UNKNOWN** - Must verify AssemblyAI has signed BAA
- AssemblyAI offers HIPAA-compliant services but requires explicit BAA
- Default service is **NOT HIPAA-compliant**
- Must use dedicated HIPAA endpoints with additional configuration

**Immediate Action Required**:
```
1. Contact AssemblyAI to execute Business Associate Agreement
2. Verify HIPAA-compliant tier is enabled on account
3. Configure redact_pii option in transcription requests
4. Enable content_safety_labels for additional PHI detection
5. Document BAA execution date and review schedule
```

#### 2. **Audio File Storage on Third-Party CDN (HIGH RISK)**
**Risk**: Audio files stored indefinitely on AssemblyAI's CDN
- No control over retention period
- No verified deletion mechanism
- Potential unauthorized access if CDN security compromised

**HIPAA Requirement**:
- §164.310(d)(1) - Device and Media Controls
- §164.316(b)(2) - Retention and Disposal

**Mitigation Steps**:
```
1. IMMEDIATE: Request AssemblyAI's data retention policy in writing
2. Configure automatic deletion after transcription (if supported)
3. RECOMMENDED: Download audio to secure local storage before uploading to AssemblyAI
4. Delete from AssemblyAI CDN immediately after successful transcription
5. Implement local encrypted storage with controlled retention
```

**Implementation Changes Needed**:
```python
# Add to discussions.py after receiving transcript
def _delete_assemblyai_audio(audio_url):
    """Delete audio file from AssemblyAI CDN per HIPAA retention policy"""
    # Use AssemblyAI delete API endpoint
    headers = {"Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"}
    response = requests.delete(audio_url, headers=headers)
    if response.status_code != 204:
        logger.error(f"Failed to delete audio from AssemblyAI: {audio_url}")
        # Flag for manual review
```

#### 3. **Transcript Data in Application Database (MEDIUM RISK)**
**Risk**: Full transcripts stored in PostgreSQL `statements` table
- Contains verbatim PHI from audio recordings
- Accessible to database administrators
- Included in database backups

**HIPAA Requirements**:
- §164.312(a)(2)(iv) - Encryption of PHI at rest
- §164.312(e)(2)(ii) - Encryption of PHI in transit

**Required Controls**:
```
✓ Database encryption at rest (verify PostgreSQL config)
✓ Encrypted backups with separate key management
✓ TLS/SSL for all database connections
✓ Audit logging of database access
✓ Role-based access control (limit who can query statements table)
✓ Regular access reviews and audit log monitoring
```

**Additional Hardening**:
```python
# Consider field-level encryption for Statement.text
from cryptography.fernet import Fernet

class Statement(db.Model):
    _text_encrypted = db.Column('text', db.LargeBinary)

    @property
    def text(self):
        return decrypt_field(self._text_encrypted)

    @text.setter
    def text(self, value):
        self._text_encrypted = encrypt_field(value)
```

#### 4. **OpenAI API for Data Extraction (CRITICAL)**
**Risk**: Statement text sent to OpenAI GPT-4o-mini for clinical data extraction
- PHI transmitted to another third party
- OpenAI's data retention and training policies

**HIPAA Requirement**: BAA required for OpenAI API usage with PHI

**Current Status**: ❌ **UNKNOWN** - Must verify OpenAI BAA
- OpenAI offers HIPAA-compliant API tier
- Requires explicit opt-in and signed BAA
- Zero data retention (ZDR) must be configured

**Immediate Action Required**:
```
1. Execute Business Associate Agreement with OpenAI
2. Enable HIPAA-compliant API endpoints
3. Configure zero data retention (ZDR)
4. Document in compliance records
5. Review OpenAI's HIPAA compliance documentation
```

#### 5. **Client-Side API Key Exposure (MEDIUM RISK)**
**Risk**: AssemblyAI API key sent to browser JavaScript
- Malicious user could extract key
- Use key to upload arbitrary content
- Potential abuse for non-clinical purposes

**Current Implementation**: [discussions.py:646-658](../training/routes/discussions.py#L646-L658)
```python
@login_required
@roles_required('ROLE_AUDITOR')
def upload_token():
    return jsonify({
        'success': True,
        'api_key': current_app.config['ASSEMBLYAI_API_KEY']
    })
```

**Mitigation Options**:

**Option A: Server-Side Upload Proxy (RECOMMENDED)**
```python
@discussion_bp.route('/discussions/upload_audio', methods=['POST'])
@login_required
@roles_required('ROLE_AUDITOR')
def upload_audio_proxy():
    """Proxy audio upload to AssemblyAI without exposing API key"""
    file = request.files['audio']

    # Upload to AssemblyAI from server
    headers = {"Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"}
    response = requests.post(
        'https://api.assemblyai.com/v2/upload',
        headers=headers,
        data=file.read()
    )

    return jsonify(response.json())
```

**Option B: Temporary Scoped Tokens**
```python
# Generate time-limited, single-use upload tokens
# Requires AssemblyAI support for token-based auth
```

#### 6. **Access Logging and Audit Trail (REQUIRED)**
**Risk**: Insufficient audit trail for PHI access
- Cannot track who accessed which recordings
- No forensic capability for breach investigation

**HIPAA Requirement**: §164.312(b) - Audit Controls

**Required Implementation**:
```python
# Add to discussions.py
import logging

audit_logger = logging.getLogger('hipaa_audit')

@discussion_bp.route('/discussions/<int:id>')
@login_required
def view_discussion(id):
    discussion = Discussion.query.get_or_404(id)

    # HIPAA audit logging
    audit_logger.info(
        f"PHI_ACCESS | user={current_user.username} | "
        f"user_id={current_user.id} | discussion_id={id} | "
        f"diagram_id={discussion.diagram_id} | "
        f"action=VIEW | timestamp={datetime.utcnow().isoformat()} | "
        f"ip={request.remote_addr}"
    )

    return render_template('discussion.html', discussion=discussion)
```

**Audit Log Requirements**:
- Who accessed PHI (user ID, username)
- What PHI was accessed (discussion ID, diagram ID)
- When it was accessed (timestamp)
- Where from (IP address, user agent)
- What action was performed (VIEW, EDIT, DELETE, EXPORT)

**Log Storage**:
- Separate audit log database or write-once storage
- Encrypted at rest
- Retained for 6 years minimum (HIPAA requirement)
- Regular review by compliance officer

#### 7. **Data Minimization (BEST PRACTICE)**
**Risk**: Storing more PHI than necessary
- Full verbatim transcripts may contain excessive detail
- Audio files contain voice biometrics (additional identifier)

**HIPAA Principle**: Minimum necessary standard

**Recommendations**:
```
1. De-identify audio before transcription (if possible)
2. Redact specific PHI from transcripts post-processing
3. Delete audio files after successful transcription
4. Consider summarization instead of full transcripts
5. Implement retention policies (auto-delete after X days/years)
```

**Implementation Example**:
```python
# Add to Statement model
class Statement(db.Model):
    # ... existing fields ...
    phi_redacted = db.Column(db.Boolean, default=False)
    retention_date = db.Column(db.DateTime)  # Auto-delete after this date

    @property
    def text_safe(self):
        """Return redacted version for non-privileged users"""
        if self.phi_redacted:
            return self.text
        return redact_phi(self.text)
```

### Required HIPAA Technical Safeguards Checklist

#### Encryption (§164.312(a)(2)(iv) & §164.312(e)(2)(ii))
- [ ] Database encryption at rest (PostgreSQL)
- [ ] Field-level encryption for Statement.text (optional but recommended)
- [ ] TLS 1.2+ for all API communications
- [ ] Encrypted backups with separate key management
- [ ] HTTPS only (HSTS enabled)

#### Access Controls (§164.312(a)(1))
- [ ] Strong authentication (consider MFA for AUDITOR role)
- [ ] Role-based access control (only AUDITOR can upload)
- [ ] Unique user identification (user_id tracking)
- [ ] Automatic logoff after inactivity
- [ ] Emergency access procedures documented

#### Audit Controls (§164.312(b))
- [ ] Comprehensive audit logging implemented
- [ ] Logs capture: who, what, when, where
- [ ] Separate audit log storage (tamper-proof)
- [ ] Regular audit log reviews (quarterly minimum)
- [ ] 6-year retention of audit logs

#### Integrity (§164.312(c)(1))
- [ ] Mechanism to authenticate PHI has not been altered
- [ ] Database transaction logging
- [ ] Checksums or digital signatures for audio files
- [ ] Version control for statement modifications

#### Transmission Security (§164.312(e)(1))
- [ ] TLS 1.2+ for all API endpoints
- [ ] Certificate pinning for mobile apps (if applicable)
- [ ] VPN or private network for database access
- [ ] No PHI transmitted via email or unencrypted channels

### Required HIPAA Administrative Safeguards

#### Business Associate Agreements (§164.308(b)(1))
- [ ] **AssemblyAI BAA executed** (CRITICAL - BLOCKING ISSUE)
- [ ] **OpenAI BAA executed** (CRITICAL - BLOCKING ISSUE)
- [ ] Redis hosting provider BAA (if cloud-hosted)
- [ ] PostgreSQL hosting provider BAA (if cloud-hosted)
- [ ] Any other third-party service that touches data

#### Risk Analysis (§164.308(a)(1)(ii)(A))
- [ ] Formal HIPAA risk assessment completed
- [ ] Vulnerabilities documented (use this document as starting point)
- [ ] Risk mitigation plan with priorities and timelines
- [ ] Annual reassessment scheduled

#### Workforce Training (§164.308(a)(5))
- [ ] HIPAA training for all developers with database access
- [ ] AUDITOR role users trained on PHI handling
- [ ] Breach notification procedures documented
- [ ] Regular refresher training (annually)

#### Contingency Plan (§164.308(a)(7))
- [ ] Data backup procedures (encrypted backups)
- [ ] Disaster recovery plan tested
- [ ] Emergency mode operations documented
- [ ] Data recovery procedures tested quarterly

#### Sanction Policy (§164.308(a)(1)(ii)(C))
- [ ] Policy for workforce violations documented
- [ ] Disciplinary actions defined
- [ ] Applied consistently

### Required HIPAA Physical Safeguards

#### Facility Access Controls (§164.310(a)(1))
- [ ] Server room access restricted and logged
- [ ] Video surveillance of physical servers
- [ ] Badge/keycard access system
- [ ] Visitor logs maintained

#### Workstation Security (§164.310(c))
- [ ] Developers use encrypted disk (FileVault, BitLocker)
- [ ] Screen locks after inactivity
- [ ] No PHI on unencrypted laptops or removals media
- [ ] Workstation security policy documented

#### Device and Media Controls (§164.310(d)(1))
- [ ] Media disposal procedures (secure wipe/shred)
- [ ] Media reuse procedures (degaussing, overwriting)
- [ ] Accountability for hardware disposal
- [ ] Inventory of devices containing PHI

### Breach Notification Requirements

If PHI is compromised, HIPAA requires:
- **Within 60 days**: Notify affected individuals
- **Within 60 days**: Notify HHS (if >500 individuals, immediately)
- **Document**: Nature of breach, individuals affected, mitigation steps
- **Investigate**: Root cause, how occurred, who had access

**Breach Detection Mechanisms Needed**:
```python
# Monitor for suspicious activity
- Failed authentication attempts (>5 in 10 min)
- Bulk statement exports (>100 records)
- After-hours database access
- Unusual query patterns
- API key usage from unexpected IPs
```

### Recommended Implementation Priorities

#### P0 - BLOCKING (Do NOT use with real PHI until resolved)
1. ✅ Execute Business Associate Agreement with AssemblyAI
2. ✅ Execute Business Associate Agreement with OpenAI
3. ✅ Verify HIPAA-compliant service tiers are active
4. ✅ Implement audit logging for all PHI access
5. ✅ Verify database encryption at rest

#### P1 - HIGH (Required for production)
1. Implement server-side upload proxy (remove client-side API key)
2. Configure automatic audio deletion from AssemblyAI CDN
3. Add field-level encryption for Statement.text
4. Implement MFA for AUDITOR role
5. Document and test breach notification procedures

#### P2 - MEDIUM (Important for compliance)
1. Add retention policies with automatic deletion
2. Implement PHI redaction in transcripts
3. Regular audit log reviews (quarterly)
4. Workforce HIPAA training program
5. Annual risk assessments

#### P3 - LOW (Defense in depth)
1. Consider on-premise transcription service
2. Voice biometric anonymization before upload
3. Database query monitoring and anomaly detection
4. Intrusion detection system (IDS)
5. Penetration testing (annually)

### Alternative Architecture: HIPAA-First Design

For maximum HIPAA compliance, consider this architecture:

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Client uploads audio to APPLICATION SERVER (not AssemblyAI)│
│    - No third-party involvement yet                          │
│    - Files temporarily stored in encrypted volume            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Server-side de-identification (optional)                  │
│    - Remove/beep patient names                               │
│    - Redact medical record numbers                           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Send to HIPAA-compliant AssemblyAI endpoint               │
│    - Use BAA-covered service tier                            │
│    - Enable redact_pii option                                │
│    - Set immediate deletion policy                           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Receive transcript, immediately delete audio from AssemblyAI│
│    - Verify deletion via API                                 │
│    - Delete local temporary file                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Store encrypted transcript in database                    │
│    - Field-level encryption                                  │
│    - Audit log entry created                                 │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. Extract clinical data using HIPAA-compliant OpenAI API    │
│    - Use ZDR (Zero Data Retention) endpoint                  │
│    - BAA in place                                            │
└──────────────────────────────────────────────────────────────┘
```

This alternative eliminates client-side API key exposure and provides better audit trail.

### Contact Information for BAA Execution

**AssemblyAI**:
- HIPAA Documentation: https://www.assemblyai.com/docs/security/hipaa-compliance
- Contact: enterprise@assemblyai.com
- Requires: Enterprise plan with HIPAA tier

**OpenAI**:
- HIPAA Documentation: https://openai.com/security/hipaa
- Contact: Through API platform settings
- Requires: Enable zero data retention in account settings

### Compliance Resources

- **HIPAA Security Rule**: https://www.hhs.gov/hipaa/for-professionals/security/index.html
- **Breach Notification Rule**: https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html
- **NIST Cybersecurity Framework**: Recommended complementary framework
- **HHS Audit Protocol**: https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/audit/protocol/index.html

### Disclaimer

This documentation identifies potential HIPAA compliance issues but does **not constitute legal advice**. Consult with:
- Healthcare attorney specializing in HIPAA
- Qualified HIPAA compliance officer
- Privacy/security consultant with healthcare experience

**Before using this system with real patient data, obtain professional HIPAA compliance review and certification.**
