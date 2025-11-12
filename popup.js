document.addEventListener('DOMContentLoaded', function() {
    const analyzeBtn = document.getElementById('analyzeBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const resultTitle = document.getElementById('resultTitle');
    const resultText = document.getElementById('resultText');
    const confidenceBar = document.getElementById('confidenceBar');
    const confidenceText = document.getElementById('confidenceText');
    const analysisTime = document.getElementById('analysisTime');
    const redFlagsDiv = document.getElementById('redFlags');

    // Check if we're on a job page and enable/disable button
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        const currentTab = tabs[0];
        const isJobPage = isJobListingPage(currentTab.url);
        
        if (!isJobPage) {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = 'Navigate to a job page first';
        }
    });

    analyzeBtn.addEventListener('click', async function() {
        loadingDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        analyzeBtn.disabled = true;

        try {
            const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
            
            const results = await chrome.scripting.executeScript({
                target: {tabId: tab.id},
                function: extractJobData
            });

            const jobData = results[0].result;
            
            if (!jobData || !jobData.text) {
                throw new Error('Could not extract job information from this page');
            }

            // Display the job title we're analyzing
            console.log('Analyzing job:', jobData.title);
            
            const analysisResult = await analyzeJobWithAPI(jobData.text, jobData.title, jobData.company);
            displayResult(analysisResult, jobData);

        } catch (error) {
            displayError(error.message);
        } finally {
            loadingDiv.style.display = 'none';
            analyzeBtn.disabled = false;
        }
    });

    async function analyzeJobWithAPI(jobText, jobTitle, jobCompany) {
        const response = await fetch('http://localhost:5001/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                job_text: jobText,
                source: 'browser_extension'
            })
        });

        if (!response.ok) {
            throw new Error('Analysis service unavailable');
        }

        const result = await response.json();
        // Add job info to result for verification
        result.jobTitle = jobTitle;
        result.jobCompany = jobCompany;
        return result;
    }

    function displayResult(result, jobData) {
        const isScam = result.prediction === 'fake';
        const confidencePercent = Math.round(result.confidence * 100);
        
        // Clean up the messy reasoning text (no emojis)
        let cleanReasoning = "No detailed analysis available.";
        
        if (result.reasoning) {
            cleanReasoning = result.reasoning
                .replace(/SCAM_PATTERN:/g, 'SCAM PATTERN:')
                .replace(/LEGITIMATE_PATTERN:/g, 'LEGITIMATE PATTERN:')
                .replace(/Key phrases: \.\.\./g, '')
                .replace(/Company: \./g, '')
                .replace(/\|/g, '\n\n')
                .replace(/\.\.\./g, '')
                .replace(/\s+/g, ' ')
                .trim();
        }

        // If reasoning is still messy, provide generic messages
        if (cleanReasoning.includes('Brand Partner') || cleanReasoning.includes('Production Engineer')) {
            cleanReasoning = isScam ? 
                "This job shows characteristics commonly associated with scam postings, such as vague company information and suspicious job titles." :
                "This job appears legitimate based on professional description and clear company details.";
        }

        // Set result style based on prediction
        resultDiv.className = 'result';
        if (isScam) {
            resultDiv.classList.add('danger');
            resultTitle.textContent = 'Potential Scam Detected';
            resultTitle.style.color = '#ef4444';
        } else if (result.confidence > 0.8) {
            resultDiv.classList.add('safe');
            resultTitle.textContent = 'Likely Legitimate';
            resultTitle.style.color = '#10b981';
        } else {
            resultDiv.classList.add('warning');
            resultTitle.textContent = 'Suspicious Elements Found';
            resultTitle.style.color = '#f59e0b';
        }

        // Update confidence bar
        confidenceBar.style.width = `${confidencePercent}%`;
        confidenceBar.style.background = isScam ? '#ef4444' : 
                                       result.confidence > 0.8 ? '#10b981' : '#f59e0b';
        
        confidenceText.textContent = `Confidence: ${confidencePercent}%`;
        analysisTime.textContent = `Time: ${result.analysis_time || result.processing_time || 'N/A'}s`;
        
        // Display job title for verification
        const jobTitleElement = document.createElement('div');
        jobTitleElement.style.cssText = 'font-size: 14px; font-weight: bold; margin-bottom: 8px; padding: 8px; background: #f8f9fa; border-radius: 4px;';
        jobTitleElement.textContent = `Job: ${jobData.title}`;
        resultText.before(jobTitleElement);
        
        // Display cleaned reasoning
        resultText.textContent = cleanReasoning;

        // Display red flags (no emojis)
        if (result.red_flags && result.red_flags.length > 0) {
            redFlagsDiv.innerHTML = '<strong>Red Flags:</strong>';
            result.red_flags.forEach(flag => {
                const cleanFlag = flag.replace(/_/g, ' ')
                                     .replace(/\b\w/g, l => l.toUpperCase());
                const flagElement = document.createElement('div');
                flagElement.className = 'red-flag';
                flagElement.textContent = `• ${cleanFlag}`;
                redFlagsDiv.appendChild(flagElement);
            });
        } else {
            redFlagsDiv.innerHTML = '';
        }

        resultDiv.style.display = 'block';
    }

    function displayError(message) {
        resultDiv.className = 'result danger';
        resultTitle.textContent = 'Analysis Failed';
        resultTitle.style.color = '#ef4444';
        resultText.textContent = message;
        confidenceText.textContent = 'Confidence: N/A';
        analysisTime.textContent = 'Time: N/A';
        redFlagsDiv.innerHTML = '';
        resultDiv.style.display = 'block';
    }

    function isJobListingPage(url) {
        const jobPatterns = [
            /linkedin\.com\/jobs/,
            /indeed\.com\/viewjob/,
            /glassdoor\.com\/Job/,
            /monster\.com\/jobs/,
            /ziprecruiter\.com\/jobs/
        ];
        return jobPatterns.some(pattern => pattern.test(url));
    }
});

// Function to be injected into the page
function extractJobData() {
    const jobData = {
        title: '',
        company: '',
        description: '',
        text: ''
    };

    // Try to extract from LinkedIn
    if (window.location.hostname.includes('linkedin.com')) {
        const titleEl = document.querySelector('.jobs-details-top-card__job-title');
        const companyEl = document.querySelector('.jobs-details-top-card__company-url');
        const descEl = document.querySelector('.jobs-description-content__text');
        
        jobData.title = titleEl?.innerText || '';
        jobData.company = companyEl?.innerText || '';
        jobData.description = descEl?.innerText || '';
    }
    // Try to extract from Indeed
    else if (window.location.hostname.includes('indeed.com')) {
        const titleEl = document.querySelector('.jobsearch-JobInfoHeader-title');
        const companyEl = document.querySelector('[data-company-name]');
        const descEl = document.querySelector('#jobDescriptionText');
        
        jobData.title = titleEl?.innerText || '';
        jobData.company = companyEl?.innerText || '';
        jobData.description = descEl?.innerText || '';
    }
    // Try to extract from Glassdoor
    else if (window.location.hostname.includes('glassdoor.com')) {
        const titleEl = document.querySelector('.jobTitle');
        const companyEl = document.querySelector('.employerName');
        const descEl = document.querySelector('.jobDescriptionContent');
        
        jobData.title = titleEl?.innerText || '';
        jobData.company = companyEl?.innerText || '';
        jobData.description = descEl?.innerText || '';
    }

    // Combine all text for analysis
    jobData.text = `TITLE: ${jobData.title} | COMPANY: ${jobData.company} | DESCRIPTION: ${jobData.description}`;
    
    return jobData;
}
