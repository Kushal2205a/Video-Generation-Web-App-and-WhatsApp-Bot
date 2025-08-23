class VideoGenerator {
    constructor(){
        this.currentJobID = null;
        this.pollingInterval = null;
        this.initializeElements();
        this.attachEventListeners(); 
    }

    initializeElements(){
        this.promptInput = document.getElementById("promptInput") ; 
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

    attachEventListeners(){
        // Click button for generating a Video
        this.generateBtn.addEventListener("click", ()=> this.generateVideo());

        // Click "Enter" key in input box to generate video
        this.promptInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter"){
                this.generateVideo(); 
            }
        });

        // Download Button
        this.downloadBtn.addEventListener('click', ()=> this.downloadVideo());

        //Generate new button 
        this.generateNewBtn.addEventListener('click', ()=> this.resetInterface()); 

    }

    async generateVideo(){
        const prompt = this.promptInput.ariaValueMax.trim();

        if (!prompt) {
            alert('Please Enter a prompt'); 
            return ; 
        }

        if (prompt.length > 200) {
            alert('Prompt should be below 200')
            return ;
        }

        try {
            // Loading State
            this.setLoadingState(true); 
            this.showStatusSection(); 
            this.hideVideoSection(); 


            // API call
            const response = await fetch('/api/genrate-video', {
                method : "POST",
                headers : {
                    'Content-Type' : 'application/json'
                }, 
                body : JSON.stringify({ prompt })
            });

            if(!response.ok){
                const error_data = await response.json(); 
                throw new Error(error_data.error || 'HTTP error, status : ${response.status}');
            }

            const data = await response.json(); 
            this.currentJobID = data.job_id; 

            // Start polling for status 
            this.startPollingStatus();

        }

        catch (error){
            console.error('Error generating video : ', error);
            this.setLoadingState(false); 

        }
    }

}
