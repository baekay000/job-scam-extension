// Content script for JobTrust AI - Automatic + Manual Analysis
console.log('JobTrust AI content script loaded');

class JobTrustAnalyzer {
    constructor() {
        this.analyzedUrls = new Set();
        this.isAnalyzing = false;
        this.init();
    }

    init() {
        console.log('Initializing JobTrust analyzer...');
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeAnalyzer());
        } else {
            this.initializeAnalyzer();
        }
    }

    initializeAnalyzer() {
        try {
            if (this.isJobDetailPage()) {
                console.log('Job detail page detected - starting FULLY AUTOMATIC analysis');
                this.showLoadingIndicator();
                // Wait for page to fully load, then analyze
                setTimeout(() => this.analyzeCurrentJob(), 2000);
            } else {
                // Not a job detail page, show manual input option
                this.showManualInputOption();
            }
        } catch (error) {
            console.error('Error initializing analyzer:', error);
        }
    }

    isJobDetailPage() {
        const url = window.location.href;
        
        // URL patterns for job detail pages
        if (url.includes('/jobs/view/') || 
            url.includes('/viewjob') ||
            url.includes('/job/') && !url.includes('/jobs')) {
            return true;
        }
        
        // Check for job description content
        const descriptionElements = document.querySelectorAll(
            '#jobDescriptionText, .job-description, .jobs-description'
        );
        
        for (const element of descriptionElements) {
            if (element.textContent && element.textContent.length > 300) {
                return true;
            }
        }
        
        return false;
    }

    showManualInputOption() {
        // Only show on pages that might have job content but aren't auto-detected
        if (document.body.textContent && document.body.textContent.length > 500) {
            this.showFloatingInputBox();
        }
    }

    showFloatingInputBox() {
        const existingInput = document.getElementById('jobtrust-manual-input');
        if (existingInput) return;

        const inputBox = document.createElement('div');
        inputBox.id = 'jobtrust-manual-input';
        inputBox.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border: 2px solid #2563eb;
            border-radius: 12px;
            padding: 20px;
            z-index: 10000;
            max-width: 400px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            line-height: 1.5;
        `;

        inputBox.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">🛡️</span>
                <span style="font-size: 16px; color: #2563eb;">JobTrust AI</span>
            </div>
            
            <div style="margin-bottom: 12px; color: #4b5563;">
                Want to analyze job text? Paste it below:
            </div>
            
            <textarea 
                id="jobtrust-text-input" 
                placeholder="Paste job description, email, or any job-related text here..."
                style="
                    width: 100%;
                    height: 120px;
                    padding: 12px;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    font-family: inherit;
                    font-size: 14px;
                    resize: vertical;
                    margin-bottom: 12px;
                "
            ></textarea>
            
            <div style="display: flex; gap: 8px;">
                <button 
                    id="jobtrust-analyze-btn"
                    style="
                        flex: 1;
                        background: #2563eb;
                        color: white;
                        border: none;
                        padding: 10px;
                        border-radius: 6px;
                        font-size: 13px;
                        cursor: pointer;
                        font-weight: 600;
                    "
                >
                    Analyze Text
                </button>
                <button 
                    onclick="this.parentElement.parentElement.remove()"
                    style="
                        background: #6b7280;
                        color: white;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 13px;
                        cursor: pointer;
                        font-weight: 600;
                    "
                >
                    ×
                </button>
            </div>
            
            <div style="margin-top: 8px; text-align: center;">
                <div style="font-size: 11px; color: #9ca3af;">
                    Or use the extension popup for more options
                </div>
            </div>
        `;

        document.body.appendChild(inputBox);

        // Add event listener to the analyze button
        const analyzeBtn = document.getElementById('jobtrust-analyze-btn');
        const textArea = document.getElementById('jobtrust-text-input');
        
        analyzeBtn.addEventListener('click', () => {
            const text = textArea.value.trim();
            if (text.length < 50) {
                this.showTemporaryMessage('Please enter at least 50 characters of job text.');
                return;
            }
            
            this.analyzeManualText(text, inputBox);
        });

        // Auto-remove after 30 seconds if not used
        setTimeout(() => {
            if (inputBox.parentElement && !document.activeElement === textArea) {
                inputBox.style.opacity = '0.7';
                setTimeout(() => {
                    if (inputBox.parentElement) {
                        inputBox.remove();
                    }
                }, 2000);
            }
        }, 30000);
    }

    async analyzeManualText(text, inputBox) {
        if (this.isAnalyzing) return;
        
        this.isAnalyzing = true;

        try {
            // Show loading state
            inputBox.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; justify-content: center;">
                        <span>🛡️</span>
                        <span>JobTrust AI</span>
                    </div>
                    <div style="width: 24px; height: 24px; border: 3px solid #f3f3f3; border-top: 3px solid #2563eb; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 12px auto;"></div>
                    <div>Analyzing job text...</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 8px;">This may take 1-2 minutes</div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            `;

            const result = await this.sendToBackgroundForAnalysis({
                text: text,
                title: 'Manual Input',
                company: 'Unknown',
                url: window.location.href
            });

            this.displayResultsAutomatically(result, {
                title: 'Manual Analysis',
                company: 'User Provided Text',
                description: text.substring(0, 200) + '...'
            });
            
            // Remove the input box
            if (inputBox.parentElement) {
                inputBox.remove();
            }
            
        } catch (error) {
            console.error('Manual analysis failed:', error);
            this.showTemporaryMessage('Manual analysis failed: ' + error.message);
            
            // Reset the input box
            if (inputBox.parentElement) {
                inputBox.remove();
                this.showFloatingInputBox();
            }
        } finally {
            this.isAnalyzing = false;
        }
    }

    showLoadingIndicator() {
        this.removeExistingIndicators();
        
        const loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'jobtrust-loading';
        loadingIndicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #2563eb;
            color: white;
            padding: 16px;
            border-radius: 8px;
            z-index: 10000;
            max-width: 300px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            border: 2px solid #1d4ed8;
        `;

        loadingIndicator.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                <span>🛡️</span>
                <span>JobTrust AI</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                <div style="width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top: 2px solid white; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px;"></div>
                <span>Analyzing job posting...</span>
            </div>
            <div style="font-size: 12px; opacity: 0.9;">
                This may take 1-2 minutes
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;

        document.body.appendChild(loadingIndicator);
    }

    async analyzeCurrentJob() {
        if (this.isAnalyzing) return;
        
        const currentUrl = window.location.href;
        if (this.analyzedUrls.has(currentUrl)) {
            this.removeExistingIndicators();
            return;
        }

        this.isAnalyzing = true;

        try {
            const jobData = this.extractJobData();
            
            if (jobData.text && jobData.text.length > 100) {
                console.log('Starting FULLY AUTOMATIC analysis...');
                
                // Update loading message
                this.updateLoadingMessage('Sending for analysis...');
                
                // Use the WORKING approach: send to background script
                const result = await this.sendToBackgroundForAnalysis(jobData);
                
                console.log('Automatic analysis complete:', result);
                this.displayResultsAutomatically(result, jobData);
                this.analyzedUrls.add(currentUrl);
                
            } else {
                this.showTemporaryMessage('Not enough job information found for analysis.');
                // Show manual input option since auto-analysis didn't work
                this.showFloatingInputBox();
            }
        } catch (error) {
            console.error('Automatic analysis failed:', error);
            this.showTemporaryMessage('Automatic analysis failed. Try manual input below.');
            // Show manual input option when auto-analysis fails
            this.showFloatingInputBox();
        } finally {
            this.isAnalyzing = false;
        }
    }

    extractJobData() {
        const jobData = {
            title: '',
            company: '',
            description: '',
            text: '',
            url: window.location.href
        };

        // Indeed.com extraction
        if (window.location.hostname.includes('indeed.com')) {
            jobData.title = document.querySelector('.jobsearch-JobInfoHeader-title, h1.jobTitle, [data-testid="jobsearch-JobInfoHeader-title"]')?.textContent?.trim() || '';
            jobData.company = document.querySelector('[data-company-name], .companyName, [data-testid="company-name"]')?.textContent?.trim() || '';
            jobData.description = document.querySelector('#jobDescriptionText, .job-description, .jobsearch-JobComponent-description')?.textContent?.trim() || '';
        }
        // LinkedIn.com extraction  
        else if (window.location.hostname.includes('linkedin.com')) {
            jobData.title = document.querySelector('.jobs-details-top-card__job-title, .job-title, .jobs-unified-top-card__job-title')?.textContent?.trim() || '';
            jobData.company = document.querySelector('.jobs-details-top-card__company-url, .jobs-details-top-card__company-name, .jobs-unified-top-card__company-name')?.textContent?.trim() || '';
            jobData.description = document.querySelector('.jobs-description-content__text, .description__text, .jobs-description')?.textContent?.trim() || '';
        }

        // Fallback: if no structured description, get main content
        if (!jobData.description || jobData.description.length < 200) {
            const mainContent = document.querySelector('main, #main, .job-details, .jobs-details, .description-container') || document.body;
            jobData.description = mainContent.textContent?.substring(0, 2500) || '';
        }

        jobData.text = `
JOB TITLE: ${jobData.title}
COMPANY: ${jobData.company}
URL: ${jobData.url}
DESCRIPTION: ${jobData.description}
        `.trim();

        console.log('Extracted job data:', {
            title: jobData.title,
            company: jobData.company,
            descLength: jobData.description.length,
            textLength: jobData.text.length
        });

        return jobData;
    }

    sendToBackgroundForAnalysis(jobData) {
        return new Promise((resolve, reject) => {
            console.log('Sending job data to background script for analysis...');
            
            chrome.runtime.sendMessage({
                action: 'analyzeJob',
                jobText: jobData.text.substring(0, 3500),
                jobTitle: jobData.title,
                jobCompany: jobData.company,
                source: 'automatic'
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error('Runtime error:', chrome.runtime.lastError);
                    reject(new Error(chrome.runtime.lastError.message));
                } else if (response && response.error) {
                    console.error('Response error:', response.error);
                    reject(new Error(response.error));
                } else if (response) {
                    console.log('Background analysis response received');
                    resolve(response);
                } else {
                    console.error('No response received from background script');
                    reject(new Error('No response from analysis service'));
                }
            });
        });
    }

    updateLoadingMessage(message) {
        const loadingElement = document.getElementById('jobtrust-loading');
        if (loadingElement) {
            const textElement = loadingElement.querySelector('span');
            if (textElement) {
                textElement.textContent = message;
            }
        }
    }

    displayResultsAutomatically(analysis, jobData) {
        this.removeExistingIndicators();
    
        if (!analysis || analysis.error) {
            this.showTemporaryMessage('Analysis incomplete. Proceed with caution.');
            return;
        }
    
        const isScam = analysis.prediction === 'fake';
        const confidencePercent = Math.round(analysis.confidence * 100);
        
        console.log(`Displaying automatic results: ${isScam ? 'SCAM' : 'LEGIT'} with ${confidencePercent}% confidence`);
    
        const resultsDiv = document.createElement('div');
        resultsDiv.id = 'jobtrust-results';
        resultsDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${isScam ? '#fef2f2' : '#f0fdf4'};
            border: 3px solid ${isScam ? '#ef4444' : '#10b981'};
            padding: 20px;
            border-radius: 12px;
            z-index: 10000;
            max-width: 400px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            line-height: 1.5;
        `;
    
        const statusColor = isScam ? '#ef4444' : '#10b981';
        const statusText = isScam ? '🚩 POTENTIAL SCAM' : '✅ LIKELY LEGITIMATE';
        const advice = isScam 
            ? 'We recommend being very cautious with this job posting. Look for red flags like upfront payments, poor grammar, or unrealistic promises.'
            : 'This job appears to be legitimate based on our analysis.';
    
        resultsDiv.innerHTML = `
            <div style="display: flex; align-items: center; margin-bottom: 16px; gap: 8px;">
                <span style="font-size: 24px;">🛡️</span>
                <div style="font-weight: bold; font-size: 18px; color: #2563eb;">JobTrust AI</div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-weight: bold; font-size: 16px; color: ${statusColor}; margin-bottom: 8px;">
                    ${statusText}
                </div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <div style="font-size: 12px; color: #6b7280;">Confidence:</div>
                    <div style="font-weight: bold; color: ${statusColor};">${confidencePercent}%</div>
                </div>
                <div style="height: 8px; background: #e5e7eb; border-radius: 4px;">
                    <div style="height: 100%; width: ${confidencePercent}%; background: ${statusColor}; border-radius: 4px; transition: width 0.5s ease;"></div>
                </div>
            </div>
            
            ${jobData.title ? `<div style="margin-bottom: 6px;"><strong>Job:</strong> ${jobData.title}</div>` : ''}
            ${jobData.company ? `<div style="margin-bottom: 12px;"><strong>Company:</strong> ${jobData.company}</div>` : ''}
            
            <div style="margin-bottom: 16px; padding: 12px; background: rgba(255,255,255,0.8); border-radius: 8px; border: 1px solid rgba(0,0,0,0.1);">
                <div style="font-weight: bold; margin-bottom: 6px; color: #374151;">Analysis Summary:</div>
                <div style="font-size: 13px; line-height: 1.4; color: #4b5563;">
                    ${analysis.reasoning ? this.cleanReasoning(analysis.reasoning) : advice}
                </div>
            </div>
            
            <div style="display: flex; gap: 8px;">
                <button id="closeResultsBtn" style="flex: 1; background: #6b7280; color: white; border: none; padding: 10px; border-radius: 6px; font-size: 13px; cursor: pointer; font-weight: 600; transition: background 0.2s;">
                    Close
                </button>
            </div>
            
            <div style="margin-top: 12px; text-align: center;">
                <div style="font-size: 11px; color: #9ca3af;">
                    🔍 ${jobData.title ? 'Automatically analyzed' : 'Manually analyzed'}
                </div>
            </div>
        `;
    
        document.body.appendChild(resultsDiv);
    
        // Add click event to close button - THIS IS THE FIX
        document.getElementById('closeResultsBtn').addEventListener('click', function() {
            resultsDiv.remove();
        });
    
        // KEEP THIS PART - Auto-remove after 3 minutes
        setTimeout(() => {
            if (resultsDiv.parentElement) {
                resultsDiv.style.opacity = '0.7';
                setTimeout(() => {
                    if (resultsDiv.parentElement) {
                        resultsDiv.remove();
                    }
                }, 2000);
            }
        }, 180000);
    }

    cleanReasoning(reasoning) {
        if (!reasoning) return 'No detailed analysis available.';
        
        // Clean up the reasoning text
        return reasoning
            .replace(/SCAM_PATTERN:/g, '🚩 ')
            .replace(/LEGITIMATE_PATTERN:/g, '✅ ')
            .replace(/\|/g, '\n\n')
            .replace(/\.\.\./g, '')
            .substring(0, 300) + '...';
    }

    showTemporaryMessage(message) {
        this.removeExistingIndicators();
        
        const messageDiv = document.createElement('div');
        messageDiv.id = 'jobtrust-message';
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #f59e0b;
            color: white;
            padding: 16px;
            border-radius: 8px;
            z-index: 10000;
            max-width: 300px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 2px solid #d97706;
        `;

        messageDiv.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                <span>🛡️</span>
                <span>JobTrust AI</span>
            </div>
            <div>${message}</div>
        `;

        document.body.appendChild(messageDiv);

        setTimeout(() => {
            if (messageDiv.parentElement) {
                messageDiv.remove();
            }
        }, 8000);
    }

    removeExistingIndicators() {
        const elements = document.querySelectorAll('#jobtrust-loading, #jobtrust-results, #jobtrust-message, #jobtrust-manual-input');
        elements.forEach(el => el.remove());
    }
}

// Initialize automatic analyzer
new JobTrustAnalyzer();
