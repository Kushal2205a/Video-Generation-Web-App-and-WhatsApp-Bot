class VideoGenerator {
    constructor() {
        this.currentJobID = null;
        this.pollingInterval = null;
        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        this.promptInput = document.getElementById("promptInput");
        this.generateBtn = document.getElementById("generateBtn");
        this.btnText = document.querySelector(".btn-text");
        this.btnLoader = document.querySelector(".btn-loader");
        this.statusSection = document.getElementById("statusSection");
        this.statusMessage = document.getElementById("statusMessage");
        this.progressFill = document.getElementById("progressFill");
        this.videoSection = document.getElementById("videoSection");
        this.generatedVideo = document.getElementById("generatedVideo");
        this.downloadBtn = document.getElementById("downloadBtn");
        this.generateNewBtn = document.getElementById("generateNewBtn");
    }

    attachEventListeners() {
        // Click button for generating a Video
        this.generateBtn.addEventListener("click", () => this.generateVideo());
        
        // Click "Enter" key in input box to generate video
        this.promptInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                this.generateVideo();
            }
        });

        // Download Button
        this.downloadBtn.addEventListener('click', () => this.downloadVideo());
        
        // Generate new button
        this.generateNewBtn.addEventListener('click', () => this.resetInterface());
    }

    async generateVideo() {
        const prompt = this.promptInput.value.trim();
        
        if (!prompt) {
            alert('Please Enter a prompt');
            return;
        }

        if (prompt.length > 200) {
            alert('Prompt should be below 200 characters');
            return;
        }

        try {
            // Loading State
            this.setLoadingState(true);
            this.showStatusSection();
            this.hideVideoSection();
            
            // API call
            const response = await fetch('/api/generate-video', {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) {
                const error_data = await response.json();
                throw new Error(error_data.detail || `HTTP error, status: ${response.status}`);
            }

            const data = await response.json();
            this.currentJobID = data.job_id;
            
            // Start polling for status
            this.startPollingStatus();

        } catch (error) {
            console.error('Error generating video:', error);
            this.showError(`Failed to generate video: ${error.message}`);
            this.setLoadingState(false);
        }
    }

    startPollingStatus() {
        this.updateStatus('Started video generation', 10);
        
        this.pollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${this.currentJobID}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP error, status: ${response.status}`);
                }

                const status = await response.json();
                
                if (status.status === 'processing') {
                    const currentProgress = this.getProgressPercentage();
                    const newProgress = Math.min(85, currentProgress + 5);
                    this.updateStatus(status.message, newProgress);
                } else if (status.status === 'completed') {
                    this.handleVideoComplete(status);
                    this.stopPollingStatus();
                } else if (status.status === 'error') {
                    this.showError(status.message);
                    this.stopPollingStatus();
                }

            } catch (error) {
                console.error('Error polling status:', error);
                this.showError(`Failed to get status: ${error.message}`);
                this.stopPollingStatus();
            }
        }, 3000);
    }

    stopPollingStatus() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
        this.setLoadingState(false);
    }

    handleVideoComplete(status) {
        this.updateStatus('Video generation completed', 100);
        
        setTimeout(() => {
            this.generatedVideo.src = status.video_url;
            this.showVideoSection();
        }, 1000);
    }

    downloadVideo() {
        if (this.currentJobID) {
            const downloadURL = `/api/download/${this.currentJobID}`;
            const link = document.createElement('a');
            link.href = downloadURL;
            link.download = `video_${Date.now()}.mp4`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    resetInterface() {
        this.currentJobID = null;
        this.promptInput.value = '';
        this.hideStatusSection();
        this.hideVideoSection();
        this.setLoadingState(false);
        this.promptInput.focus();
    }

    // UI update Methods
    setLoadingState(loading) {
        this.generateBtn.disabled = loading;
        
        if (loading) {
            this.btnText.style.display = 'none';
            this.btnLoader.style.display = 'inline-flex';
        } else {
            this.btnText.style.display = 'inline';
            this.btnLoader.style.display = 'none';
        }
    }

    showStatusSection() {
        this.statusSection.style.display = 'block';
        this.statusSection.scrollIntoView({ behavior: 'smooth' });
    }

    hideStatusSection() {
        this.statusSection.style.display = 'none';
    }

    showVideoSection() {
        this.videoSection.style.display = 'block';
        this.videoSection.scrollIntoView({ behavior: 'smooth' });
    }

    hideVideoSection() {
        this.videoSection.style.display = 'none';
    }

    updateStatus(message, progress = 0) {
        this.statusMessage.textContent = message;
        this.progressFill.style.width = `${progress}%`;
    }

    getProgressPercentage() {
        return parseInt(this.progressFill.style.width) || 0;
    }

    showError(message) {
        this.updateStatus(`${message}`, 0);
        this.setLoadingState(false);
        
        setTimeout(() => {
            this.hideStatusSection();
        }, 8000);
    }
}

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    new VideoGenerator();
    
    // Loading animation
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    setTimeout(() => {
        document.body.style.opacity = '1';
    }, 100);
});
