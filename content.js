// Content script for JobTrust AI - works on job listing pages too
console.log('JobTrust AI content script loaded');

class JobTrustAnalyzer {
    constructor() {
        this.analyzedUrls = new Set();
        this.isAnalyzing = false;
        this.observer = null;
        this.init();
    }

    init() {
        console.log('Initializing JobTrust analyzer...');
        
        const pageType = this.getPageType();
        console.log('Page type detected:', pageType);
        
        if (pageType === 'job-detail') {
            this.showLoadingIndicator();
            this.scheduleAnalysis();
        } else if (pageType === 'job-listing') {
            console.log('Job listing page detected - adding analyze buttons to job cards');
            this.setupListingPageObserver();
        }
        
        this.setupObservers();
        this.setupUrlChangeListener();
    }

    getPageType() {
        const url = window.location.href;
        const path = window.location.pathname;
        
        // Job detail pages
        if (url.includes('/viewjob') || 
            url.includes('/job/') && url.includes('jk=') ||
            path.includes('/jobs/view/') ||
            (path.includes('/Job/') && !path.includes('-jobs')) ||
            url.includes('/jobs/') && url.includes('/view/')) {
            return 'job-detail';
        }
        
        // Job listing/search pages
        if (path.includes('/jobs-search') ||
            path.includes('/jobs/') && !path.includes('/view/') ||
            (path.includes('/Job/') && path.includes('-jobs')) ||
            url.includes('/jobs?') ||
            url.includes('/jobs-search?') ||
            url.includes('/job-search') ||
            document.querySelector('.job_results, .jobsearch-Results, [data-test="jobListing"], .jobs-search-results')) {
            return 'job-listing';
        }
        
        return 'unknown';
    }

    setupListingPageObserver() {
        // Add analyze buttons to existing job cards
        this.addAnalyzeButtonsToPreviews();
        
        // Watch for new job cards being added (infinite scroll)
        this.observer = new MutationObserver((mutations) => {
            let newCards = false;
            
            for (const mutation of mutations) {
                if (mutation.type === 'childList') {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === 1) {
                            // Check if this is a job card or contains job cards
                            if (this.isJobCard(node) || node.querySelector && this.hasJobCards(node)) {
                                newCards = true;
                                break;
                            }
                        }
                    }
                }
                if (newCards) break;
            }
            
            if (newCards) {
                setTimeout(() => {
                    this.addAnalyzeButtonsToPreviews();
                }, 500);
            }
        });

        this.observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    isJobCard(element) {
        if (!element.classList) return false;
        
        const classList = Array.from(element.classList);
        const jobKeywords = ['job', 'card', 'listing', 'result', 'item'];
        const text = element.textContent || '';
        
        return classList.some(className => 
            jobKeywords.some(keyword => className.toLowerCase().includes(keyword))
        ) || text.includes('Apply') || text.includes('$') || text.includes('/yr') || text.includes('/hr');
    }

    hasJobCards(element) {
        const selectors = [
            '.job_card',
            '.job-card',
            '.job_listing',
            '.job-listing',
            '.job_result',
            '.job-result',
            '[data-test*="job"]',
            '[class*="job"]'
        ];
        
        return selectors.some(selector => element.querySelector(selector));
    }

    addAnalyzeButtonsToPreviews() {
        console.log('Adding analyze buttons to job cards...');
        
        // ZipRecruiter selectors
        const zipRecruiterCards = document.querySelectorAll('.job_content, .job_result, [class*="job-listing"]');
        // Indeed selectors  
        const indeedCards = document.querySelectorAll('.job_seen_beacon, .result, [data-jk]');
        // LinkedIn selectors
        const linkedinCards = document.querySelectorAll('.job-card-container, .jobs-search-results__list-item, [data-job-id]');
        // Glassdoor selectors
        const glassdoorCards = document.querySelectorAll('.react-job-listing, .jobListing, [data-test="job-listing"]');
        // Generic job cards
        const genericCards = document.querySelectorAll('[class*="job"], [class*="listing"], .result, .card');
        
        const allCards = [...zipRecruiterCards, ...indeedCards, ...linkedinCards, ...glassdoorCards, ...genericCards];
        
        console.log(`Found ${allCards.length} potential job cards`);
        
        allCards.forEach((card, index) => {
            // Skip if already has our button or doesn't look like a job card
            if (card.querySelector('.jobtrust-analyze-btn') || !this.looksLikeJobCard(card)) {
                return;
            }
            
            this.addAnalyzeButtonToCard(card, index);
        });
    }

    looksLikeJobCard(card) {
        const text = card.textContent || '';
        const hasJobKeywords = text.includes('Apply') || text.includes('$') || text.includes('yr') || text.includes('hr') || text.includes('Full-time') || text.includes('Part-time');
        const hasReasonableSize = text.length > 100 && text.length < 5000;
        
        return hasJobKeywords && hasReasonableSize;
    }

    addAnalyzeButtonToCard(card, index) {
        const button = document.createElement('button');
        button.className = 'jobtrust-analyze-btn';
        button.innerHTML = '🔍 Analyze';
        button.style.cssText = `
            background: #2563eb;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            margin: 8px 0;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-weight: 600;
            transition: background 0.2s;
            display: block;
            width: 100%;
            max-width: 120px;
        `;

        button.addEventListener('mouseenter', () => {
            button.style.background = '#1d4ed8';
        });

        button.addEventListener('mouseleave', () => {
            button.style.background = '#2563eb';
        });

        button.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            button.innerHTML = 'Analyzing...';
            button.disabled = true;
            
            const jobData = this.extractJobDataFromCard(card);
            console.log('Extracted from card:', jobData);
            
            if (jobData.text && jobData.text.length > 50) {
                this.showFloatingAnalysis(jobData, card, button);
            } else {
                this.showTooltip(button, 'Not enough job details in preview');
                button.innerHTML = '🔍 Analyze';
                button.disabled = false;
            }
        });

        // Find a good place to insert the button
        const applyButton = card.querySelector('a[href*="apply"], button[class*="apply"], .apply, [class*="apply"]');
        if (applyButton) {
            applyButton.parentNode.insertBefore(button, applyButton.nextSibling);
        } else {
            // Try to find the bottom of the card
            const lastElement = card.lastElementChild;
            if (lastElement) {
                card.appendChild(button);
            } else {
                card.insertAdjacentElement('beforeend', button);
            }
        }
    }

    extractJobDataFromCard(card) {
        const jobData = {
            title: '',
            company: '',
            location: '',
            salary: '',
            description: '',
            text: ''
        };

        // Get all text content first
        const cardText = card.textContent || '';

        // Extract title - look for h2, h3, or large bold text
        jobData.title = this.getTextFromElement(card, [
            'h2', 'h3', 'h4',
            '.job_title', '.job-title', '.title',
            '[class*="title"]',
            '.job_header', '.job-header'
        ]) || this.extractTitleFromText(cardText);

        // Extract company
        jobData.company = this.getTextFromElement(card, [
            '.company', '.employer', '.company_name',
            '[class*="company"]',
            '.job_company', '.job-company'
        ]) || this.extractCompanyFromText(cardText);

        // Extract location
        jobData.location = this.getTextFromElement(card, [
            '.location', '.job_location', '.job-location',
            '[class*="location"]'
        ]) || this.extractLocationFromText(cardText);

        // Extract salary
        jobData.salary = this.getTextFromElement(card, [
            '.salary', '.compensation', '.pay',
            '[class*="salary"]', '[class*="compensation"]'
        ]) || this.extractSalaryFromText(cardText);

        // Extract description/job type
        jobData.description = this.getTextFromElement(card, [
            '.job_snippet', '.job-snippet', '.description',
            '.job_type', '.job-type',
            '[class*="description"]', '[class*="snippet"]'
        ]) || this.extractDescriptionFromText(cardText);

        // If we still don't have much description, use the first 200 chars of card text
        if (!jobData.description || jobData.description.length < 20) {
            jobData.description = cardText.substring(0, 200).trim();
        }

        // Build analysis text
        jobData.text = `JOB TITLE: ${jobData.title} | COMPANY: ${jobData.company} | LOCATION: ${jobData.location} | SALARY: ${jobData.salary} | DESCRIPTION: ${jobData.description}`;
        
        return jobData;
    }

    extractTitleFromText(text) {
        // Look for patterns that might indicate a job title
        const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
        
        // First non-empty line is often the title
        if (lines.length > 0 && lines[0].length < 100) {
            return lines[0];
        }
        
        // Look for text before "Apply" or salary
        const applyIndex = text.indexOf('Apply');
        if (applyIndex > 0) {
            const beforeApply = text.substring(0, applyIndex).trim();
            const lines = beforeApply.split('\n');
            if (lines.length > 0) {
                return lines[lines.length - 1].trim();
            }
        }
        
        return 'Unknown Position';
    }

    extractCompanyFromText(text) {
        // Look for company names - usually after title, before location
        const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
        
        if (lines.length > 1 && lines[1].length < 50) {
            return lines[1];
        }
        
        // Look for common company indicators
        if (text.includes('•')) {
            const parts = text.split('•');
            if (parts.length > 1) {
                return parts[1].trim().split('\n')[0];
            }
        }
        
        return 'Unknown Company';
    }

    extractLocationFromText(text) {
        // Look for city, state patterns
        const locationMatch = text.match(/([A-Z][a-z]+(?: [A-Z][a-z]+)*),? ([A-Z]{2})/);
        if (locationMatch) {
            return locationMatch[0];
        }
        
        // Look for "City • State" pattern
        const cityStateMatch = text.match(/([A-Z][a-z]+) • ([A-Z][a-z]+)/);
        if (cityStateMatch) {
            return cityStateMatch[0].replace(' •', ',');
        }
        
        return 'Location not specified';
    }

    extractSalaryFromText(text) {
        // Look for salary patterns
        const salaryMatch = text.match(/\$[\d,]+(?:K)?(?: - \$[\d,]+(?:K)?)?(?:\/yr|\/hr|\/year|\/hour)?/);
        if (salaryMatch) {
            return salaryMatch[0];
        }
        
        // Look for "K/yr" patterns
        const kMatch = text.match(/\d+K\/yr/);
        if (kMatch) {
            return kMatch[0];
        }
        
        return 'Salary not specified';
    }

    extractDescriptionFromText(text) {
        // Get text that's not title, company, location, or salary
        const lines = text.split('\n').map(line => line.trim()).filter(line => 
            line.length > 10 && 
            line.length < 200 &&
            !line.includes('Apply') &&
            !line.match(/\$[\d,]/) &&
            !line.match(/[A-Z][a-z]+,? [A-Z]{2}/)
        );
        
        return lines.slice(0, 2).join(' | ') || 'Job details not available in preview';
    }

    getTextFromElement(element, selectors) {
        for (const selector of selectors) {
            const found = element.querySelector(selector);
            if (found && found.textContent && found.textContent.trim()) {
                return found.textContent.trim();
            }
        }
        return '';
    }

    async showFloatingAnalysis(jobData, card, button) {
        const existingFloating = document.getElementById('jobtrust-floating');
        if (existingFloating) {
            existingFloating.remove();
        }

        const floatingDiv = document.createElement('div');
        floatingDiv.id = 'jobtrust-floating';
        floatingDiv.style.cssText = `
            position: absolute;
            background: white;
            border: 2px solid #2563eb;
            border-radius: 8px;
            padding: 16px;
            z-index: 10001;
            max-width: 320px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            line-height: 1.4;
        `;

        // Position near the card
        const rect = card.getBoundingClientRect();
        floatingDiv.style.top = (rect.bottom + window.scrollY + 10) + 'px';
        floatingDiv.style.left = (rect.left + window.scrollX) + 'px';

        floatingDiv.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 12px; color: #2563eb; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px;">
                JobTrust AI - Quick Analysis
            </div>
            <div style="margin-bottom: 8px;">
                <strong>Job:</strong> ${jobData.title || 'Unknown'}
            </div>
            <div style="margin-bottom: 8px;">
                <strong>Company:</strong> ${jobData.company || 'Unknown'}
            </div>
            <div style="margin-bottom: 12px;">
                <strong>Status:</strong> 
                <span style="color: #6b7280; font-weight: bold;">ANALYZING...</span>
            </div>
            <div class="jobtrust-spinner" style="
                width: 20px;
                height: 20px;
                border: 3px solid #e5e7eb;
                border-top: 3px solid #2563eb;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 12px auto;
            "></div>
            <div style="font-size: 11px; color: #6b7280; text-align: center;">
                Analyzing job preview for scam indicators...
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;

        document.body.appendChild(floatingDiv);

        try {
            const response = await chrome.runtime.sendMessage({
                action: 'analyzeJob',
                jobText: jobData.text,
                jobTitle: jobData.title,
                jobCompany: jobData.company
            });

            this.updateFloatingAnalysis(floatingDiv, response, jobData);
            button.innerHTML = '🔍 Analyze';
            button.disabled = false;
        } catch (error) {
            floatingDiv.innerHTML = `
                <div style="color: #ef4444; margin-bottom: 12px;">
                    <strong>Analysis failed:</strong> ${error.message}
                </div>
                <button onclick="this.parentElement.remove()" style="background: #6b7280; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; width: 100%;">
                    Close
                </button>
            `;
            button.innerHTML = '🔍 Analyze';
            button.disabled = false;
        }
    }

    updateFloatingAnalysis(floatingDiv, analysis, jobData) {
        if (!analysis || analysis.error) {
            floatingDiv.innerHTML = `
                <div style="color: #ef4444; margin-bottom: 12px;">
                    Analysis error: ${analysis?.error || 'Unknown error'}
                </div>
                <button onclick="this.parentElement.remove()" style="background: #6b7280; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; width: 100%;">
                    Close
                </button>
            `;
            return;
        }

        const isScam = analysis.prediction === 'fake';
        const confidencePercent = Math.round(analysis.confidence * 100);
        const statusColor = isScam ? '#ef4444' : (analysis.confidence > 0.7 ? '#10b981' : '#f59e0b');
        const statusText = isScam ? 'POTENTIAL SCAM' : (analysis.confidence > 0.7 ? 'LIKELY SAFE' : 'USE CAUTION');

        floatingDiv.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 12px; color: #2563eb; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px;">
                JobTrust AI - Quick Analysis
            </div>
            
            <div style="margin-bottom: 8px;">
                <strong>Job:</strong> ${jobData.title || 'Unknown'}
            </div>
            
            <div style="margin-bottom: 8px;">
                <strong>Company:</strong> ${jobData.company || 'Unknown'}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Status:</strong> 
                <span style="color: ${statusColor}; font-weight: bold; font-size: 14px;">
                    ${statusText}
                </span>
            </div>
            
            <div style="margin-bottom: 12px;">
                <strong>Confidence:</strong> ${confidencePercent}%
                <div style="height: 6px; background: #e5e7eb; border-radius: 3px; margin-top: 4px;">
                    <div style="height: 100%; width: ${confidencePercent}%; 
                        background: ${statusColor}; 
                        border-radius: 3px; transition: width 0.3s ease;"></div>
                </div>
            </div>
            
            <div style="font-size: 11px; color: #6b7280; margin-bottom: 12px; padding: 8px; background: #f8f9fa; border-radius: 4px;">
                <em>Note: This is a quick analysis based on limited preview information. For full analysis, visit the job details page.</em>
            </div>
            
            <button onclick="this.parentElement.remove()" style="background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 12px; cursor: pointer; width: 100%; font-weight: 600;">
                Close Analysis
            </button>
        `;
    }

    showTooltip(button, message) {
        const tooltip = document.createElement('div');
        tooltip.textContent = message;
        tooltip.style.cssText = `
            position: absolute;
            background: #374151;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 10002;
            white-space: nowrap;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        `;

        const rect = button.getBoundingClientRect();
        tooltip.style.top = (rect.top + window.scrollY - 40) + 'px';
        tooltip.style.left = (rect.left + window.scrollX) + 'px';

        document.body.appendChild(tooltip);

        setTimeout(() => {
            tooltip.remove();
        }, 3000);
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            border: 2px solid #1d4ed8;
        `;

        loadingIndicator.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 8px;">
                JobTrust AI - Analyzing Job
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <div class="jobtrust-spinner" style="
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-top: 2px solid white;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-right: 8px;
                "></div>
                <span>Extracting job information...</span>
            </div>
            <div id="jobtrust-job-info" style="font-size: 12px; background: rgba(255,255,255,0.2); padding: 8px; border-radius: 4px;">
                Looking for job details on this page...
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;

        document.body.appendChild(loadingIndicator);
        
        setTimeout(() => {
            this.updateLoadingWithJobInfo();
        }, 500);
    }

    updateLoadingWithJobInfo() {
        const jobInfoElement = document.getElementById('jobtrust-job-info');
        if (jobInfoElement) {
            const jobData = this.extractJobData();
            
            let infoHTML = '';
            if (jobData.title) {
                infoHTML += `<div><strong>Job:</strong> ${jobData.title}</div>`;
            }
            if (jobData.company) {
                infoHTML += `<div><strong>Company:</strong> ${jobData.company}</div>`;
            }
            if (!jobData.title && !jobData.company) {
                infoHTML = '<div>Scanning page content...</div>';
            }
            
            jobInfoElement.innerHTML = infoHTML;
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

        const hostname = window.location.hostname;

        // Indeed.com
        if (hostname.includes('indeed.com')) {
            jobData.title = this.getText([
                '.jobsearch-JobInfoHeader-title',
                'h1.jobTitle',
                '[data-testid="jobsearch-JobInfoHeader-title"]',
                'h1'
            ]);
            
            jobData.company = this.getText([
                '[data-company-name]',
                '.companyName',
                '.jobsearch-CompanyReview--heading',
                '[data-testid="company-name"]'
            ]);
            
            jobData.description = this.getText([
                '#jobDescriptionText',
                '.job-description',
                '.jobsearch-JobComponent-description',
                '[data-testid="job-description"]'
            ]);
        }
        // LinkedIn.com
        else if (hostname.includes('linkedin.com')) {
            jobData.title = this.getText([
                '.jobs-details-top-card__job-title',
                '.job-title',
                'h1'
            ]);
            
            jobData.company = this.getText([
                '.jobs-details-top-card__company-url',
                '.jobs-details-top-card__company-name',
                '.jobs-unified-top-card__company-name'
            ]);
            
            jobData.description = this.getText([
                '.jobs-description-content__text',
                '.description__text',
                '.jobs-description'
            ]);
        }
        // Glassdoor.com
        else if (hostname.includes('glassdoor.com')) {
            jobData.title = this.getText([
                '.jobTitle',
                'h1[data-test="job-title"]',
                'h1'
            ]);
            
            jobData.company = this.getText([
                '.employerName',
                '.css-16nw49e',
                '[data-test="employer-name"]'
            ]);
            
            jobData.description = this.getText([
                '.jobDescriptionContent',
                '.desc',
                '.job-description'
            ]);
        }

        // Fallback
        if (!jobData.title) {
            jobData.title = this.getText(['h1', '.title', '.job-title']);
        }
        if (!jobData.description) {
            jobData.description = this.getDescriptionFallback();
        }

        jobData.text = `JOB TITLE: ${jobData.title} | COMPANY: ${jobData.company} | DESCRIPTION: ${jobData.description}`;
        
        return jobData;
    }

    getText(selectors) {
        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent && element.textContent.trim()) {
                return element.textContent.trim();
            }
        }
        return '';
    }

    getDescriptionFallback() {
        const contentSelectors = [
            'main',
            '[role="main"]',
            '.content',
            '.main-content',
            '#main-content'
        ];
        
        for (const selector of contentSelectors) {
            const element = document.querySelector(selector);
            if (element) {
                const text = element.textContent || '';
                if (text.length > 500) {
                    return text.trim();
                }
            }
        }
        return '';
    }

    removeExistingIndicators() {
        const loading = document.getElementById('jobtrust-loading');
        const badge = document.getElementById('jobtrust-badge');
        const floating = document.getElementById('jobtrust-floating');
        if (loading) loading.remove();
        if (badge) badge.remove();
        if (floating) floating.remove();
    }

    setupObservers() {
        // Observer for job detail pages
        const detailObserver = new MutationObserver((mutations) => {
            let shouldAnalyze = false;
            
            for (const mutation of mutations) {
                if (mutation.type === 'childList') {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === 1 && this.containsJobContent(node)) {
                            shouldAnalyze = true;
                            break;
                        }
                    }
                }
                if (shouldAnalyze) break;
            }
            
            if (shouldAnalyze) {
                this.showLoadingIndicator();
                this.scheduleAnalysis();
            }
        });

        detailObserver.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    containsJobContent(element) {
        const text = element.textContent || '';
        const selectors = [
            '.job-description',
            '.jobs-description',
            '[class*="description"]',
            '.job-details'
        ];
        
        if (selectors.some(selector => element.matches?.(selector) || element.querySelector?.(selector))) {
            return true;
        }
        
        const jobKeywords = ['job description', 'qualifications', 'requirements', 'responsibilities'];
        return jobKeywords.some(keyword => text.toLowerCase().includes(keyword)) && text.length > 200;
    }

    setupUrlChangeListener() {
        let currentUrl = window.location.href;
        
        setInterval(() => {
            if (window.location.href !== currentUrl) {
                currentUrl = window.location.href;
                const pageType = this.getPageType();
                if (pageType === 'job-detail') {
                    this.showLoadingIndicator();
                    this.scheduleAnalysis();
                } else if (pageType === 'job-listing') {
                    this.addAnalyzeButtonsToPreviews();
                }
            }
        }, 1000);
    }

    scheduleAnalysis() {
        if (this.analysisTimeout) {
            clearTimeout(this.analysisTimeout);
        }
        
        this.analysisTimeout = setTimeout(() => {
            this.analyzeCurrentJob();
        }, 2000);
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
            this.updateLoadingToAnalyzing();
            
            const jobData = this.extractJobData();
            
            if (jobData.text && jobData.text.length > 300) {
                console.log('Sending for analysis:', {
                    title: jobData.title,
                    company: jobData.company,
                    textLength: jobData.text.length
                });

                const response = await chrome.runtime.sendMessage({
                    action: 'analyzeJob',
                    jobText: jobData.text,
                    jobTitle: jobData.title,
                    jobCompany: jobData.company
                });

                this.displayResults(response, jobData);
                this.analyzedUrls.add(currentUrl);
            } else {
                this.showError('Not enough job information found on this page');
            }
        } catch (error) {
            console.error('Analysis failed:', error);
            this.showError('Analysis failed: ' + error.message);
        } finally {
            this.isAnalyzing = false;
        }
    }

    updateLoadingToAnalyzing() {
        const loadingElement = document.getElementById('jobtrust-loading');
        if (loadingElement) {
            const analyzingText = loadingElement.querySelector('span');
            if (analyzingText) {
                analyzingText.textContent = 'Analyzing for potential scams...';
            }
        }
    }

    displayResults(analysis, jobData) {
        this.removeExistingIndicators();

        if (!analysis || analysis.error) {
            this.showError('Analysis failed: ' + (analysis?.error || 'Unknown error'));
            return;
        }

        const isScam = analysis.prediction === 'fake';
        const confidencePercent = Math.round(analysis.confidence * 100);
        
        const badge = this.createResultsBadge(analysis, jobData, isScam, confidencePercent);
        document.body.appendChild(badge);
    }

    createResultsBadge(analysis, jobData, isScam, confidencePercent) {
        const badge = document.createElement('div');
        badge.id = 'jobtrust-badge';
        
        badge.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${isScam ? '#fee2e2' : (analysis.confidence > 0.8 ? '#d1fae5' : '#fef3c7')};
            border: 2px solid ${isScam ? '#ef4444' : (analysis.confidence > 0.8 ? '#10b981' : '#f59e0b')};
            padding: 16px;
            border-radius: 8px;
            z-index: 10000;
            max-width: 350px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            line-height: 1.4;
        `;

        const cleanReasoning = this.cleanReasoning(analysis.reasoning);
        
        badge.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 12px; border-bottom: 1px solid #ccc; padding-bottom: 8px;">
                <div style="font-size: 16px; color: #2563eb;">JobTrust AI - Analysis Complete</div>
                <div style="font-size: 13px; color: #666; margin-top: 4px;">
                    <strong>Job:</strong> ${jobData.title || 'Unknown'}
                </div>
                ${jobData.company ? `<div style="font-size: 13px; color: #666;"><strong>Company:</strong> ${jobData.company}</div>` : ''}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Status:</strong> 
                <span style="color: ${isScam ? '#ef4444' : (analysis.confidence > 0.8 ? '#10b981' : '#f59e0b')}; font-weight: bold;">
                    ${isScam ? 'POTENTIAL SCAM' : (analysis.confidence > 0.8 ? 'LIKELY LEGITIMATE' : 'SUSPICIOUS ELEMENTS FOUND')}
                </span>
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Confidence:</strong> ${confidencePercent}%
                <div style="height: 6px; background: #e5e7eb; border-radius: 3px; margin-top: 4px;">
                    <div style="height: 100%; width: ${confidencePercent}%; 
                        background: ${isScam ? '#ef4444' : (analysis.confidence > 0.8 ? '#10b981' : '#f59e0b')}; 
                        border-radius: 3px;"></div>
                </div>
            </div>
            
            <div style="margin-bottom: 12px;">
                <strong>Analysis:</strong>
                <div style="max-height: 120px; overflow-y: auto; font-size: 12px; margin-top: 6px; padding: 8px; background: rgba(255,255,255,0.7); border-radius: 4px; border: 1px solid #ddd;">
                    ${cleanReasoning}
                </div>
            </div>
            
            <div style="text-align: right;">
                <button id="close-badge" style="background: #6b7280; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer;">
                    Close
                </button>
            </div>
        `;

        badge.querySelector('#close-badge').addEventListener('click', () => {
            badge.remove();
        });

        return badge;
    }

    showError(message) {
        this.removeExistingIndicators();
        
        const errorBadge = document.createElement('div');
        errorBadge.id = 'jobtrust-badge';
        errorBadge.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #fee2e2;
            border: 2px solid #ef4444;
            padding: 16px;
            border-radius: 8px;
            z-index: 10000;
            max-width: 300px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
        `;

        errorBadge.innerHTML = `
            <div style="font-weight: bold; color: #ef4444; margin-bottom: 8px;">Analysis Failed</div>
            <div>${message}</div>
            <button onclick="this.parentElement.remove()" style="background: #6b7280; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 12px; cursor: pointer; margin-top: 8px;">
                Close
            </button>
        `;

        document.body.appendChild(errorBadge);
    }

    cleanReasoning(reasoning) {
        if (!reasoning) return "No detailed analysis available.";
        
        return reasoning
            .replace(/SCAM_PATTERN:/g, '<span style="color: #ef4444; font-weight: bold;">SCAM PATTERN:</span>')
            .replace(/LEGITIMATE_PATTERN:/g, '<span style="color: #10b981; font-weight: bold;">LEGITIMATE PATTERN:</span>')
            .replace(/\|/g, '<br><br>')
            .replace(/\.\.\./g, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    isJobPage(url) {
        const jobPatterns = [
            /indeed\.com\/viewjob/,
            /indeed\.com\/job\/[^\/]+-[a-f0-9]+/,
            /linkedin\.com\/jobs\/view/,
            /linkedin\.com\/jobs\/collections/,
            /glassdoor\.com\/Job\//,
            /monster\.com\/jobs\//,
            /ziprecruiter\.com\/jobs\//
        ];
        return jobPatterns.some(pattern => pattern.test(url));
    }
}

// Initialize
new JobTrustAnalyzer();