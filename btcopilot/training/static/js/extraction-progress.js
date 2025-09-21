// Statement extraction progress tracker
class ExtractionProgress {
    constructor() {
        this.pollInterval = null;
        this.discussionId = null;
        this.progressBarElement = null;
        this.progressTextElement = null;
        this.containerElement = null;
    }

    // Initialize progress tracking for a discussion
    init(discussionId, containerId = 'progress-container') {
        this.discussionId = discussionId;
        this.containerElement = document.getElementById(containerId);
        
        if (!this.containerElement) {
            console.warn(`Container element '${containerId}' not found`);
            return;
        }
        
        // Create progress bar UI
        this.createProgressBar();
        
        // Start polling
        this.startPolling();
        
        // Check initial status
        this.checkProgress();
    }
    
    createProgressBar() {
        const progressHtml = `
            <div class="progress" id="progress-bar">
                <div class="notification is-info is-light">
                    <h5 class="subtitle is-6 mb-2">
                        <span class="icon"><i class="fas fa-cog fa-spin"></i></span>
                        <span>Extracting data from conversation...</span>
                    </h5>
                    <progress class="progress is-info is-medium" id="progress-bar" value="0" max="100"></progress>
                    <p class="help mt-1" id="progress-text">Processing statements...</p>
                </div>
            </div>
        `;
        
        this.containerElement.innerHTML = progressHtml;
        this.progressBarElement = document.getElementById('progress-bar');
        this.progressTextElement = document.getElementById('progress-text');
    }
    
    async checkProgress() {
        try {
            const response = await fetch(`/training/discussions/${this.discussionId}/progress`);
            
            if (!response.ok) {
                console.error('Failed to fetch extraction progress:', response.status);
                this.stopPolling();
                return;
            }
            
            const data = await response.json();
            this.updateProgress(data);
            
        } catch (error) {
            console.error('Error checking extraction progress:', error);
            this.stopPolling();
        }
    }
    
    updateProgress(data) {
        if (!this.progressBarElement || !this.progressTextElement) return;
        
        // Update progress bar
        this.progressBarElement.value = data.percent_complete;
        
        // Update text
        if (data.total === 0) {
            this.progressTextElement.textContent = 'No statements to process';
            this.hideProgressBar();
        } else if (data.pending === 0) {
            this.progressTextElement.textContent = `All ${data.total} statements processed`;
            this.hideProgressBar();
        } else {
            this.progressTextElement.textContent = `Processed ${data.processed} of ${data.total} statements`;
            
            // Schedule background job if needed and not already processing
            if (data.pending > 0 && !data.is_processing) {
                this.triggerBackgroundJob();
            }
        }
    }
    
    hideProgressBar() {
        // Stop polling
        this.stopPolling();
        
        // Fade out and remove after a delay
        if (this.containerElement) {
            const progressEl = this.containerElement.querySelector('.progress');
            if (progressEl) {
                progressEl.style.transition = 'opacity 0.5s ease-out';
                progressEl.style.opacity = '0';
                
                setTimeout(() => {
                    this.containerElement.innerHTML = '';
                }, 500);
            }
        }
    }
    
    startPolling() {
        // Poll every 2 seconds
        this.pollInterval = setInterval(() => {
            this.checkProgress();
        }, 2000);
    }
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
    
    async triggerBackgroundJob() {
        // This would trigger the background job to continue processing
        // In a real implementation, this might call an endpoint to ensure
        // the background job is scheduled
        console.log('Triggering background extraction job...');
    }
    
    // Clean up when leaving the page
    destroy() {
        this.stopPolling();
        if (this.containerElement) {
            this.containerElement.innerHTML = '';
        }
    }
}

// Create global instance
window.extractionProgress = new ExtractionProgress();

// Auto-initialize if discussion ID is available in the page
document.addEventListener('DOMContentLoaded', () => {
    // Look for discussion ID in page data
    const discussionEl = document.querySelector('[data-discussion-id]');
    if (discussionEl) {
        const discussionId = discussionEl.dataset.discussionId;
        window.extractionProgress.init(discussionId);
    }
});