document.addEventListener('DOMContentLoaded', function() {
    const analyzeCurrentPageBtn = document.getElementById('analyzeCurrentPage');
    const analyzeTextBtn = document.getElementById('analyzeTextBtn');
    const jobTextInput = document.getElementById('jobTextInput');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const autoStatus = document.getElementById('autoStatus');
    const manualStatus = document.getElementById('manualStatus');
    
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabs = document.querySelectorAll('.tab-content');

    // Tab switching
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            
            // Update buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Update tabs
            tabs.forEach(tab => tab.classList.remove('active'));
            document.getElementById(`${tabName}-tab`).classList.add('active');
            
            // Clear results when switching tabs
            resultDiv.style.display = 'none';
            loadingDiv.style.display = 'none';
        });
    });

    // Auto-extract job info when popup opens
    autoExtractJobInfo();

    analyzeCurrentPageBtn.addEventListener('click', analyzeCurrentPage);
    analyzeTextBtn.addEventListener('click', analyzeTextInput);

    async function autoExtractJobInfo() {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            if (isJobSite(tab.url)) {
                autoStatus.textContent = '✅ Ready to analyze this job page';
                analyzeCurrentPageBtn.disabled = false;
                
                // Try to pre-fill the manual tab with extracted text
                try {
                    const jobData = await chrome.scripting.executeScript({
                        target: { tabId: tab.id },
                        function: extractJobDataFromPage
                    });
                    
                    if (jobData && jobData[0] && jobData[0].result) {
                        const extracted = jobData[0].result;
                        if (extracted.text && extracted.text.length > 100) {
                            // Pre-fill manual text area with extracted data
                            jobTextInput.placeholder = `Auto-extracted from current page:\n\n${extracted.text.substring(0, 300)}...\n\nYou can edit this text or paste your own.`;
                        }
                    }
                } catch (error) {
                    console.log('Could not pre-fill text area:', error);
                }
            } else {
                autoStatus.textContent = '⚠️ Not a supported job site. Use manual input.';
                analyzeCurrentPageBtn.disabled = true;
            }
        } catch (error) {
            console.log('Auto-extract error:', error);
            autoStatus.textContent = '❌ Error detecting page. Use manual input.';
            analyzeCurrentPageBtn.disabled = true;
        }
    }

    function isJobSite(url) {
        return url.includes('indeed.com') || 
               url.includes('linkedin.com') || 
               url.includes('glassdoor.com') ||
               url.includes('ziprecruiter.com') ||
               url.includes('monster.com');
    }

    async function analyzeCurrentPage() {
        showLoading('Extracting job information from page...');
        
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            const jobData = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                function: extractJobDataFromPage
            });

            if (jobData && jobData[0] && jobData[0].result) {
                const extractedData = jobData[0].result;
                if (extractedData.text && extractedData.text.length > 100) {
                    showLoading('Analyzing job posting...');
                    await sendForAnalysis(extractedData.text, extractedData);
                } else {
                    showError('Not enough job information found on this page. Please use the manual input tab.');
                }
            } else {
                showError('Could not extract job information from this page. Please use the manual input tab.');
            }
        } catch (error) {
            showError('Error analyzing page: ' + error.message);
        }
    }

    async function analyzeTextInput() {
        const text = jobTextInput.value.trim();
        if (text.length < 50) {
            showManualStatus('❌ Please enter at least 50 characters of job description.', true);
            return;
        }

        showLoading('Analyzing job text...');
        await sendForAnalysis(text, { title: 'Manual Input', company: 'User Provided' });
    }

    async function sendForAnalysis(jobText, jobData) {
        try {
            // Direct fetch from popup (popup can make localhost requests)
            const response = await fetch('http://localhost:5001/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    job_text: jobText.substring(0, 4000),
                    source: 'popup'
                })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();
            showResult(result, jobData);
        } catch (error) {
            showError('Analysis failed: ' + error.message + '\n\nPlease ensure the Flask server is running on port 5001.');
        }
    }

    function showLoading(message = 'Analyzing...') {
        loadingDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        loadingDiv.innerHTML = `
            <div class="spinner"></div>
            <div style="font-weight: 600; margin-bottom: 4px;">${message}</div>
            <div style="font-size: 12px; color: #6b7280;">This may take 1-2 minutes</div>
        `;
    }

    function showResult(analysis, jobData) {
        loadingDiv.style.display = 'none';
        resultDiv.style.display = 'block';

        const isScam = analysis.prediction === 'fake';
        const confidencePercent = Math.round(analysis.confidence * 100);
        const statusColor = isScam ? '#ef4444' : '#10b981';
        const statusText = isScam ? 'POTENTIAL SCAM' : 'LIKELY LEGITIMATE';
        const statusEmoji = isScam ? '🚩' : '✅';

        let resultHTML = `
            <div style="text-align: center; margin-bottom: 20px; padding: 16px; background: ${isScam ? '#fef2f2' : '#f0fdf4'}; border-radius: 8px; border: 2px solid ${statusColor};">
                <div style="font-size: 48px; margin-bottom: 8px;">${statusEmoji}</div>
                <div style="font-size: 18px; font-weight: bold; color: ${statusColor}; margin-bottom: 8px;">
                    ${statusText}
                </div>
                <div style="font-size: 14px; color: #6b7280;">
                    Confidence: ${confidencePercent}%
                </div>
                <div style="height: 6px; background: #e5e7eb; border-radius: 3px; margin: 8px 0;">
                    <div style="height: 100%; width: ${confidencePercent}%; background: ${statusColor}; border-radius: 3px;"></div>
                </div>
            </div>
        `;

        if (jobData.title || jobData.company) {
            resultHTML += `<div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px; font-size: 14px;">`;
            if (jobData.title) resultHTML += `<div style="margin-bottom: 4px;"><strong>Job:</strong> ${jobData.title}</div>`;
            if (jobData.company) resultHTML += `<div><strong>Company:</strong> ${jobData.company}</div>`;
            resultHTML += `</div>`;
        }

        if (analysis.reasoning) {
            resultHTML += `
                <div style="margin-bottom: 16px;">
                    <div style="font-weight: bold; margin-bottom: 8px; color: #374151;">Analysis Details:</div>
                    <div style="font-size: 12px; line-height: 1.4; padding: 12px; background: #f8f9fa; border-radius: 6px; max-height: 200px; overflow-y: auto; border: 1px solid #e5e7eb;">
                        ${analysis.reasoning.replace(/\n/g, '<br>')}
                    </div>
                </div>
            `;
        }

        resultHTML += `
            <div style="display: flex; gap: 8px;">
                <button id="analyzeAnotherBtn" style="flex: 1; background: #2563eb;">Analyze Another</button>
                <button id="closePopupBtn" style="flex: 1; background: #6b7280;">Close</button>
            </div>
        `;

        resultDiv.innerHTML = resultHTML;

        // Add event listeners to the new buttons
        document.getElementById('analyzeAnotherBtn').addEventListener('click', function() {
            // Reset to initial state
            resultDiv.style.display = 'none';
            loadingDiv.style.display = 'none';
            // Clear the text area if we're in manual mode
            if (document.getElementById('manual-tab').classList.contains('active')) {
                jobTextInput.value = '';
            }
        });

        document.getElementById('closePopupBtn').addEventListener('click', function() {
            // Close the popup by removing focus (Chrome extension workaround)
            window.blur();
            // Alternative method: simulate ESC key
            setTimeout(() => {
                window.close();
            }, 100);
        });
    }

    function showError(message) {
        loadingDiv.style.display = 'none';
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `
            <div style="text-align: center; color: #ef4444; padding: 20px;">
                <div style="font-size: 48px; margin-bottom: 8px;">❌</div>
                <div style="font-weight: bold; margin-bottom: 8px; font-size: 16px;">Analysis Failed</div>
                <div style="font-size: 14px; line-height: 1.4;">${message}</div>
                <div style="display: flex; gap: 8px; margin-top: 16px;">
                    <button id="tryAgainBtn" style="flex: 1; background: #2563eb;">Try Again</button>
                    <button id="closeErrorBtn" style="flex: 1; background: #6b7280;">Close</button>
                </div>
            </div>
        `;

        // Add event listeners to error buttons
        document.getElementById('tryAgainBtn').addEventListener('click', function() {
            resultDiv.style.display = 'none';
        });

        document.getElementById('closeErrorBtn').addEventListener('click', function() {
            window.blur();
            setTimeout(() => {
                window.close();
            }, 100);
        });
    }

    function showManualStatus(message, isError = false) {
        manualStatus.textContent = message;
        manualStatus.style.color = isError ? '#ef4444' : '#6b7280';
    }
});

// Function to be injected into the page for auto-extraction
function extractJobDataFromPage() {
    const jobData = {
        title: '',
        company: '',
        description: '',
        text: ''
    };

    const url = window.location.href;

    // Indeed.com extraction
    if (url.includes('indeed.com')) {
        jobData.title = document.querySelector('.jobsearch-JobInfoHeader-title, h1.jobTitle, [data-testid="jobsearch-JobInfoHeader-title"]')?.textContent?.trim() || '';
        jobData.company = document.querySelector('[data-company-name], .companyName, [data-testid="company-name"]')?.textContent?.trim() || '';
        jobData.description = document.querySelector('#jobDescriptionText, .job-description, .jobsearch-JobComponent-description')?.textContent?.trim() || '';
    }
    // LinkedIn.com extraction
    else if (url.includes('linkedin.com')) {
        jobData.title = document.querySelector('.jobs-details-top-card__job-title, .job-title, .jobs-unified-top-card__job-title')?.textContent?.trim() || '';
        jobData.company = document.querySelector('.jobs-details-top-card__company-url, .jobs-details-top-card__company-name, .jobs-unified-top-card__company-name')?.textContent?.trim() || '';
        jobData.description = document.querySelector('.jobs-description-content__text, .description__text, .jobs-description')?.textContent?.trim() || '';
    }

    // Fallback: if no structured description, get main content
    if (!jobData.description || jobData.description.length < 200) {
        const mainContent = document.querySelector('main, #main, .job-details, .jobs-details') || document.body;
        jobData.description = mainContent.textContent?.substring(0, 2000) || '';
    }

    jobData.text = `
JOB TITLE: ${jobData.title}
COMPANY: ${jobData.company}
URL: ${url}
DESCRIPTION: ${jobData.description}
    `.trim();

    return jobData;
}
