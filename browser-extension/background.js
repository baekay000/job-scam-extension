// Background script for JobTrust AI
console.log('JobTrust AI background script loaded');

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('Background: Received message', request.action);
    
    if (request.action === 'analyzeJob') {
        console.log('Background: Analyzing job posting, text length:', request.jobText?.length);
        
        // Make the API call from background script (not subject to CSP)
        fetch('http://localhost:5001/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                job_text: request.jobText,
                source: request.source || 'browser_extension'
            })
        })
        .then(response => {
            console.log('Background: API response status:', response.status);
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Background: Analysis completed successfully');
            sendResponse(data);
        })
        .catch(error => {
            console.error('Background: Analysis failed:', error);
            sendResponse({ 
                error: error.message,
                prediction: 'error',
                confidence: 0,
                reasoning: 'Unable to analyze job posting. Please ensure the local server is running on port 5001.'
            });
        });
        
        return true; // Keep message channel open for async response
    }
});

chrome.runtime.onInstalled.addListener(() => {
    console.log('JobTrust AI extension installed');
});
