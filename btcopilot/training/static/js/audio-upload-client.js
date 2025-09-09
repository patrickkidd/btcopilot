// Audio upload entirely client-side with AssemblyAI
class AudioUploadClient {
    constructor() {
        this.uploadInProgress = false;
        this.supportedTypes = ['mp3', 'wav', 'm4a', 'mp4', 'flac', 'ogg', 'webm', 'aac'];
        this.supportedMimeTypes = [
            'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 
            'audio/mp4', 'audio/m4a', 'audio/flac', 'audio/ogg', 
            'audio/webm', 'audio/aac', 'audio/x-m4a'
        ];
    }

    validateAudioFile(file) {
        if (!file.type.startsWith('audio/')) {
            const supportedList = this.supportedTypes.join(', ').toUpperCase();
            return {
                valid: false,
                message: `Please drop an audio file. Supported formats: ${supportedList}`
            };
        }

        if (!this.supportedMimeTypes.includes(file.type)) {
            const supportedList = this.supportedTypes.join(', ').toUpperCase();
            return {
                valid: false,
                message: `Audio format "${file.type}" not supported. Supported formats: ${supportedList}`
            };
        }

        return { valid: true };
    }

    async uploadToAssemblyAI(file, apiKey) {
        // Upload directly to AssemblyAI
        const uploadResponse = await fetch('https://api.assemblyai.com/v2/upload', {
            method: 'POST',
            headers: {
                'authorization': `${apiKey}`,
            },
            body: file
        });

        if (!uploadResponse.ok) {
            const error = await uploadResponse.text();
            throw new Error(`Upload failed: ${error}`);
        }

        const uploadData = await uploadResponse.json();
        
        // Request transcription
        const transcriptResponse = await fetch('https://api.assemblyai.com/v2/transcript', {
            method: 'POST',
            headers: {
                'Authorization': `${apiKey}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                audio_url: uploadData.upload_url,
                speaker_labels: true,
                // diarization_min_speakers: 2,
                // diarization_max_speakers: 10,
                // punctuate: true,
                // format_text: true,
            })
        });

        if (!transcriptResponse.ok) {
            const error = await transcriptResponse.text();
            throw new Error(`Transcription request failed: ${error}`);
        }

        const transcriptData = await transcriptResponse.json();
        
        // Poll for completion
        return await this.pollTranscription(transcriptData.id, apiKey);
    }

    async pollTranscription(transcriptId, apiKey) {
        while (true) {
            const response = await fetch(`https://api.assemblyai.com/v2/transcript/${transcriptId}`, {
                headers: {
                    'Authorization': `${apiKey}`,
                }
            }); 
            
            const data = await response.json();
            
            if (data.status === 'completed') {
                return data;
            } else if (data.status === 'error') {
                throw new Error(`Transcription failed: ${data.error}`);
            }
            
            // Update progress
            this.updateProgress('transcribing');
            
            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }

    updateProgress(status) {
        const event = new CustomEvent('upload-progress', {
            detail: { status }
        });
        window.dispatchEvent(event);
    }

    showProgress(contextId, filename) {
        // Try to find element by user-id first, then by diagram-id
        let element = document.querySelector(`[data-user-id="${contextId}"]`);
        if (!element && contextId.startsWith('diagram-')) {
            const diagramId = contextId.replace('diagram-', '');
            element = document.querySelector(`[data-diagram-id="${diagramId}"] .audio-drop-zone`);
        }
        if (!element) return;
        
        const progressHtml = `
            <div class="upload-progress-container" style="padding: 2rem; text-align: center;">
                <div class="icon is-large has-text-primary">
                    <i class="fas fa-spinner fa-pulse fa-3x"></i>
                </div>
                <h3 class="title is-5 mt-3">Uploading: ${filename}</h3>
                <progress class="progress is-primary" max="100" id="progress-${contextId}"></progress>
                <p class="subtitle is-6 mt-2" id="status-${contextId}">Preparing upload...</p>
            </div>
        `;
        
        element.innerHTML = progressHtml;
        return element;
    }

    showError(element, error, originalContent) {
        element.innerHTML = `
            <div class="notification is-danger">
                <p><strong>Upload failed:</strong></p>
                <p>${error}</p>
                <button class="button is-small mt-3" onclick="window.location.reload()">
                    <span class="icon"><i class="fas fa-redo"></i></span>
                    <span>Try Again</span>
                </button>
            </div>
        `;
    }

    async handleFileDrop(event, context) {
        event.preventDefault();
        
        const files = event.dataTransfer.files;
        if (files.length === 0) return;
        
        const file = files[0];
        const validation = this.validateAudioFile(file);
        
        if (!validation.valid) {
            alert(validation.message);
            return;
        }
        
        if (this.uploadInProgress) {
            alert('Audio upload already in progress');
            return;
        }
        
        // Handle both user_id (legacy) and object context
        const userId = typeof context === 'object' ? context.user_id : context;
        const diagramId = typeof context === 'object' ? context.diagram_id : null;
        
        const confirmMessage = diagramId 
            ? `Upload "${file.name}" to this diagram for transcription and analysis?`
            : `Upload "${file.name}" for this user?`;
        
        if (!confirm(confirmMessage)) {
            return;
        }
        
        this.uploadInProgress = true;
        const element = this.showProgress(userId || `diagram-${diagramId}`, file.name);
        const originalContent = element.innerHTML;
        
        try {
            // Get API key
            const statusEl = document.getElementById(`status-${userId || `diagram-${diagramId}`}`);
            if (statusEl) statusEl.textContent = 'Getting upload token...';
            
            const keyResponse = await fetch('/therapist/discussions/upload_token');
            const keyData = await keyResponse.json();
            
            if (!keyData.success) {
                throw new Error(keyData.error || 'Failed to get upload token');
            }
            
            // Update progress
            const progressEl = document.getElementById(`progress-${userId || `diagram-${diagramId}`}`);
            if (progressEl) progressEl.value = 20;
            if (statusEl) statusEl.textContent = 'Uploading to transcription service...';
            
            // Upload and transcribe
            const transcriptData = await this.uploadToAssemblyAI(file, keyData.api_key);
            
            // Update progress
            if (progressEl) progressEl.value = 80;
            if (statusEl) statusEl.textContent = 'Creating discussion...';
            
            // Send transcript to server with appropriate context
            let url = '/therapist/discussions/transcript';
            const params = new URLSearchParams();
            
            params.append('title', file.name);
            if (diagramId) {
                params.append('diagram_id', diagramId);
            }
            
            if (params.toString()) {
                url += '?' + params.toString();
            }
            
            const createResponse = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(transcriptData)
            });
            
            const createData = await createResponse.json();
            if (!createData.success) {
                throw new Error(createData.error || 'Failed to create discussion');
            }
            
            // Success!
            if (progressEl) progressEl.value = 100;
            if (statusEl) statusEl.textContent = 'Complete! Processing statements...';
            
            // Show extraction progress inline
            element.innerHTML = `
                <div class="notification is-success is-light">
                    <p><strong>Upload successful!</strong></p>
                    <p>Discussion created.</p>
                </div>
                <div id="progress-container"></div>
            `;
            
            // Initialize extraction progress tracker
            if (window.extractionProgress) {
                window.extractionProgress.init(createData.discussion_id, 'progress-container');
            }
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showError(element, error.message, originalContent);
        } finally {
            this.uploadInProgress = false;
        }
    }
}

// Initialize handler
window.audioUploadClient = new AudioUploadClient();

// Helper functions for drag events
function handleAudioDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    
    // Don't style if dragging over JSON zone
    const jsonZone = event.target.closest('[ondrop*="handleJsonDrop"]');
    if (!jsonZone) {
        event.currentTarget.classList.add('drag-over');
    }
}

function handleAudioDragLeave(event) {
    event.currentTarget.classList.remove('drag-over');
}

function handleAudioDrop(event, userId) {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    
    // Check if this drop originated from the JSON drop zone
    const jsonZone = event.target.closest('[ondrop*="handleJsonDrop"]');
    if (jsonZone) {
        // This is a JSON drop, don't handle it here
        return;
    }
    
    window.audioUploadClient.handleFileDrop(event, userId);
}

// New function for diagram audio drops
function handleDiagramAudioDrop(event, diagramId) {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    
    // Check if this drop originated from the JSON drop zone
    const jsonZone = event.target.closest('[ondrop*="handleJsonDrop"]');
    if (jsonZone) {
        // This is a JSON drop, don't handle it here
        return;
    }
    
    window.audioUploadClient.handleFileDrop(event, { diagram_id: diagramId });
}

// Listen for progress updates
window.addEventListener('upload-progress', (event) => {
    const elements = document.querySelectorAll('[id^="status-"]');
    elements.forEach(el => {
        if (event.detail.status === 'transcribing' && el.textContent.includes('Uploading')) {
            el.textContent = 'Transcribing audio...';
        }
    });
});