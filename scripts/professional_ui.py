from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS, cross_origin
import pandas as pd
import io
import csv
from datetime import datetime
import os
import time
import subprocess
import re

app = Flask(__name__)
# Enable CORS for all routes - this fixes the browser extension issue
CORS(app)

# Statistics tracking
analysis_stats = {
    'total_analysis': 0,
    'scams_detected': 0,
    'total_analysis_time': 0,
    'common_patterns': {}
}

PROFESSIONAL_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobTrust AI - Job Scam Detection System</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-600: #4b5563;
            --gray-800: #1f2937;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            color: var(--gray-800);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        
        .app-container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            margin-bottom: 30px;
        }
        
        .tabs {
            display: flex;
            background: var(--gray-100);
            border-bottom: 1px solid var(--gray-200);
        }
        
        .tab {
            padding: 16px 24px;
            background: none;
            border: none;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            flex: 1;
            text-align: center;
        }
        
        .tab.active {
            background: white;
            border-bottom: 3px solid var(--primary);
            font-weight: 600;
        }
        
        .tab-content {
            display: none;
            padding: 30px;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--gray-800);
        }
        
        textarea, input[type="text"], input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px solid var(--gray-200);
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        
        textarea:focus, input:focus {
            outline: none;
            border-color: var(--primary);
        }
        
        textarea {
            height: 200px;
            resize: vertical;
            font-family: inherit;
        }
        
        .btn {
            background: var(--primary);
            color: white;
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3);
        }
        
        .btn-secondary {
            background: var(--gray-600);
        }
        
        .btn-secondary:hover {
            background: var(--gray-800);
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid var(--gray-200);
            border-top: 4px solid var(--primary);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .result {
            margin-top: 30px;
            padding: 24px;
            border-radius: 12px;
            border-left: 6px solid;
            animation: slideIn 0.5s ease;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .result-safe {
            background: #f0fdf4;
            border-color: var(--success);
        }
        
        .result-warning {
            background: #fef3c7;
            border-color: var(--warning);
        }
        
        .result-danger {
            background: #fef2f2;
            border-color: var(--danger);
        }
        
        .result h3 {
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .red-flags {
            margin-top: 16px;
        }
        
        .red-flag {
            background: white;
            padding: 8px 12px;
            margin: 4px 0;
            border-radius: 6px;
            border-left: 3px solid var(--danger);
        }
        
        .confidence-meter {
            margin: 16px 0;
        }
        
        .confidence-bar {
            height: 8px;
            background: var(--gray-200);
            border-radius: 4px;
            overflow: hidden;
        }
        
        .confidence-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }
        
        .file-upload-area {
            border: 2px dashed var(--gray-200);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .file-upload-area:hover {
            border-color: var(--primary);
            background: var(--gray-100);
        }
        
        .file-upload-area.dragover {
            border-color: var(--primary);
            background: var(--gray-100);
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 40px;
        }
        
        .feature-card {
            background: white;
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .feature-icon {
            font-size: 2.5rem;
            margin-bottom: 16px;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .tabs {
                flex-direction: column;
            }
            
            .tab-content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ JobTrust AI</h1>
            <p>Advanced Job Scam Detection System</p>
        </div>
        
        <div class="app-container">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('single-tab')">Single Job Analysis</button>
                <button class="tab" onclick="switchTab('batch-tab')">Batch Analysis</button>
                <button class="tab" onclick="switchTab('api-tab')">API Access</button>
                <button class="tab" onclick="switchTab('stats-tab')">Statistics</button>
            </div>
            
            <!-- Single Job Analysis Tab -->
            <div id="single-tab" class="tab-content active">
                <h2>Analyze Single Job Posting</h2>
                <p>Paste a job description below to check for potential scams</p>
                
                <div class="form-group">
                    <label for="jobText">Job Description:</label>
                    <textarea id="jobText" placeholder="Paste the complete job posting including company information, requirements, salary details, and contact information..."></textarea>
                </div>
                
                <button class="btn" onclick="analyzeSingleJob()">
                    🔍 Analyze Job Posting
                </button>
                
                <div id="single-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Analyzing job posting for scam indicators...</p>
                </div>
                
                <div id="single-result"></div>
            </div>
            
            <!-- Batch Analysis Tab -->
            <div id="batch-tab" class="tab-content">
                <h2>Batch Job Analysis</h2>
                <p>Upload a CSV file with multiple job postings for bulk analysis</p>
                
                <div class="file-upload-area" onclick="document.getElementById('batchFile').click()" 
                     ondrop="handleFileDrop(event)" ondragover="handleDragOver(event)">
                    <input type="file" id="batchFile" accept=".csv" style="display: none;" onchange="handleFileSelect(this.files)">
                    <div style="font-size: 3rem;">📁</div>
                    <h3>Drop CSV file here or click to upload</h3>
                    <p>CSV should have columns: job_title, company, description, requirements</p>
                </div>
                
                <div id="batch-file-info" style="margin-top: 15px;"></div>
                
                <button class="btn" onclick="analyzeBatchJobs()" id="batch-btn" disabled>
                    📊 Analyze Batch Jobs
                </button>
                
                <div id="batch-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Analyzing batch jobs... This may take a few minutes</p>
                </div>
                
                <div id="batch-result"></div>
            </div>
            
            <!-- API Access Tab -->
            <div id="api-tab" class="tab-content">
                <h2>API Access</h2>
                <p>Integrate JobTrust AI into your applications</p>
                
                <div class="form-group">
                    <label>API Endpoint:</label>
                    <input type="text" value="http://localhost:5001/analyze" readonly 
                           style="background: var(--gray-100);">
                </div>
                
                <div class="form-group">
                    <label>Example Request (cURL):</label>
                    <textarea readonly style="height: 120px; font-family: monospace; background: var(--gray-100);">
curl -X POST http://localhost:5001/analyze \\
  -H "Content-Type: application/json" \\
  -d '{
    "job_text": "Your job description here...",
    "model": "improved_rag"
  }'</textarea>
                </div>
                
                <div class="form-group">
                    <label>Example Response:</label>
                    <textarea readonly style="height: 200px; font-family: monospace; background: var(--gray-100);">
{
  "prediction": "fake",
  "confidence": 0.92,
  "red_flags": ["unrealistic_salary", "personal_contact"],
  "reasoning": "Matches known scam patterns...",
  "analysis_time": 0.45
}</textarea>
                </div>
            </div>
            
            <!-- Statistics Tab -->
            <div id="stats-tab" class="tab-content">
                <h2>System Statistics</h2>
                <p>Real-time performance and detection metrics</p>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number" id="total-analysis">0</div>
                        <div class="stat-label">Total Analysis</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="scams-detected">0</div>
                        <div class="stat-label">Scams Detected</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="accuracy-rate">0%</div>
                        <div class="stat-label">Accuracy Rate</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="avg-time">0s</div>
                        <div class="stat-label">Avg. Analysis Time</div>
                    </div>
                </div>
                
                <h3 style="margin-top: 30px;">Common Scam Patterns Detected</h3>
                <div id="common-patterns">
                    <!-- Will be populated by JavaScript -->
                </div>
            </div>
        </div>
        
        <div class="features">
            <div class="feature-card">
                <div class="feature-icon">🔍</div>
                <h3>AI-Powered Detection</h3>
                <p>Advanced machine learning models trained on thousands of job scams</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <h3>Real-Time Analysis</h3>
                <p>Get instant results with detailed reasoning and confidence scores</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🛡️</div>
                <h3>Multiple Models</h3>
                <p>Combines RAG pattern matching with fine-tuned AI models</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <h3>Batch Processing</h3>
                <p>Analyze multiple job postings simultaneously</p>
            </div>
        </div>
    </div>

    <script>
        let currentBatchFile = null;
        
        function switchTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabId).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
            
            // Load stats when stats tab is opened
            if (tabId === 'stats-tab') {
                loadStatistics();
            }
        }
        
        async function analyzeSingleJob() {
            const jobText = document.getElementById('jobText').value.trim();
            const loadingDiv = document.getElementById('single-loading');
            const resultDiv = document.getElementById('single-result');
            
            if (!jobText) {
                alert('Please enter a job description to analyze.');
                return;
            }
            
            if (jobText.length < 50) {
                alert('Please provide a more detailed job description (at least 50 characters).');
                return;
            }
            
            loadingDiv.style.display = 'block';
            resultDiv.innerHTML = '';
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ job_text: jobText })
                });
                
                const data = await response.json();
                loadingDiv.style.display = 'none';
                displaySingleResult(data);
                
            } catch (error) {
                loadingDiv.style.display = 'none';
                resultDiv.innerHTML = `
                    <div class="result result-danger">
                        <h3>❌ Analysis Failed</h3>
                        <p>Unable to analyze job posting. Please try again.</p>
                    </div>
                `;
            }
        }
        
        function displaySingleResult(data) {
            const resultDiv = document.getElementById('single-result');
            const isScam = data.prediction === 'fake';
            const confidencePercent = Math.round(data.confidence * 100);
            
            let resultClass = 'result-warning';
            let icon = '⚠️';
            let title = 'Suspicious Job';
            
            if (isScam) {
                resultClass = 'result-danger';
                icon = '❌';
                title = 'Potential Scam Detected';
            } else if (data.confidence > 0.8) {
                resultClass = 'result-safe';
                icon = '✅';
                title = 'Likely Legitimate';
            }
            
            let redFlagsHTML = '';
            if (data.red_flags && data.red_flags.length > 0) {
                redFlagsHTML = `
                    <div class="red-flags">
                        <h4>🚩 Red Flags Detected:</h4>
                        ${data.red_flags.map(flag => `
                            <div class="red-flag">${flag.replace(/_/g, ' ').toUpperCase()}</div>
                        `).join('')}
                    </div>
                `;
            }
            
            resultDiv.innerHTML = `
                <div class="result ${resultClass}">
                    <h3>${icon} ${title}</h3>
                    <p><strong>Confidence:</strong> ${confidencePercent}%</p>
                    
                    <div class="confidence-meter">
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${confidencePercent}%; background: ${
                                isScam ? '#ef4444' : data.confidence > 0.8 ? '#10b981' : '#f59e0b'
                            }"></div>
                        </div>
                    </div>
                    
                    <p><strong>Analysis:</strong> ${data.reasoning || 'No detailed reasoning available.'}</p>
                    
                    ${redFlagsHTML}
                    
                    <p><strong>Analysis Time:</strong> ${data.analysis_time || data.processing_time || 'N/A'} seconds</p>
                    
                    ${isScam ? `
                        <div style="margin-top: 16px; padding: 12px; background: #fef2f2; border-radius: 6px;">
                            <strong>⚠️ Safety Warning:</strong> This job shows strong signs of being fraudulent. 
                            Do not share personal information or send money. Report suspicious job postings to the platform.
                        </div>
                    ` : ''}
                </div>
            `;
        }
        
        function handleDragOver(event) {
            event.preventDefault();
            event.currentTarget.classList.add('dragover');
        }
        
        function handleFileDrop(event) {
            event.preventDefault();
            event.currentTarget.classList.remove('dragover');
            const files = event.dataTransfer.files;
            handleFileSelect(files);
        }
        
        function handleFileSelect(files) {
            if (files.length > 0) {
                const file = files[0];
                if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
                    currentBatchFile = file;
                    document.getElementById('batch-file-info').innerHTML = `
                        <div style="background: #f0fdf4; padding: 12px; border-radius: 8px;">
                            ✅ File selected: <strong>${file.name}</strong> (${(file.size / 1024).toFixed(1)} KB)
                        </div>
                    `;
                    document.getElementById('batch-btn').disabled = false;
                } else {
                    alert('Please select a CSV file.');
                }
            }
        }
        
        async function analyzeBatchJobs() {
            if (!currentBatchFile) {
                alert('Please select a CSV file first.');
                return;
            }
            
            const loadingDiv = document.getElementById('batch-loading');
            const resultDiv = document.getElementById('batch-result');
            
            loadingDiv.style.display = 'block';
            resultDiv.innerHTML = '';
            
            const formData = new FormData();
            formData.append('file', currentBatchFile);
            
            try {
                const response = await fetch('/analyze-batch', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'job_analysis_results.csv';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    
                    resultDiv.innerHTML = `
                        <div class="result result-safe">
                            <h3>✅ Batch Analysis Complete</h3>
                            <p>Results have been downloaded. Check your downloads folder for "job_analysis_results.csv"</p>
                        </div>
                    `;
                } else {
                    throw new Error('Batch analysis failed');
                }
                
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="result result-danger">
                        <h3>❌ Batch Analysis Failed</h3>
                        <p>Unable to process batch file. Please try again.</p>
                    </div>
                `;
            } finally {
                loadingDiv.style.display = 'none';
            }
        }
        
        async function loadStatistics() {
            try {
                const response = await fetch('/stats');
                const data = await response.json();
                
                document.getElementById('total-analysis').textContent = data.total_analysis.toLocaleString();
                document.getElementById('scams-detected').textContent = data.scams_detected.toLocaleString();
                document.getElementById('accuracy-rate').textContent = data.accuracy_rate + '%';
                document.getElementById('avg-time').textContent = data.avg_analysis_time + 's';
                
                // Display common patterns
                const patternsDiv = document.getElementById('common-patterns');
                patternsDiv.innerHTML = data.common_patterns.map(pattern => `
                    <div style="background: white; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #ef4444;">
                        <strong>${pattern.pattern}</strong> - ${pattern.count} detections
                    </div>
                `).join('');
                
            } catch (error) {
                console.error('Failed to load statistics:', error);
            }
        }
        
        // Load initial statistics
        loadStatistics();
    </script>
</body>
</html>
'''


def simple_analysis(job_text):
    """Simple pattern matching as fallback"""
    text = job_text.lower()
    scam_score = 0
    red_flags = []
    
    scam_patterns = {
        'sensitive_info_request': ['ssn', 'social security', 'bank details', 'bank account', 'routing number'],
        'unrealistic_salary': ['$8000', '$10000', '$5000 monthly', '$10000 monthly'],
        'personal_contact': ['@gmail.com', '@yahoo.com', '@hotmail.com'],
        'urgency_tactics': ['immediately', 'urgent', 'quick start', 'asap'],
        'no_qualifications': ['no experience', 'no skills', 'no background'],
        'upfront_payment': ['payment', 'fee', 'deposit', 'training materials']
    }
    
    for flag_name, patterns in scam_patterns.items():
        if any(pattern in text for pattern in patterns):
            scam_score += 0.2
            red_flags.append(flag_name)
    
    # Legitimate indicators
    legit_indicators = ['bachelor', 'degree', 'experience', 'salary', 'benefits', 'requirements']
    legit_score = sum(0.05 for indicator in legit_indicators if indicator in text)
    
    final_score = max(0.1, scam_score - legit_score)
    
    return {
        'prediction': 'fake' if final_score > 0.3 else 'real',
        'confidence': max(0.3, final_score),
        'red_flags': red_flags,
        'reasoning': f"Simple analysis: {len(red_flags)} red flags detected"
    }

def parse_rag_single_output(output):
    """Parse the output from rag_single.py into our standard format"""
    print(f"🔍 Parsing RAG output: {output}")
    
    # Default values
    prediction = 'real'
    confidence = 0.5
    reasoning_lines = []
    
    lines = output.strip().split('\n')
    
    # Parse the output more flexibly
    in_reasons_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check for verdict (case insensitive, flexible formatting)
        if re.search(r'(?i)^\s*verdict\s*:\s*(fake|real)', line):
            verdict_match = re.search(r'(?i)(fake|real)', line)
            if verdict_match:
                verdict_text = verdict_match.group(1).lower()
                prediction = 'fake' if 'fake' in verdict_text else 'real'
                print(f"🎯 Detected {prediction.upper()} verdict")
        
        # Check for reasons section
        elif re.search(r'(?i)^\s*reasons?\s*:', line):
            in_reasons_section = True
            continue
        
        # If we're in reasons section, collect bullet points
        elif in_reasons_section:
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                # Clean the reason line
                clean_line = re.sub(r'^[\-\•\*]\s*', '', line).strip()
                if clean_line and len(clean_line) > 3:  # Only add substantial reasons
                    reasoning_lines.append(clean_line)
                    print(f"📝 Added reason: {clean_line}")
            elif line and not reasoning_lines:
                # Some models might not use bullet points consistently
                reasoning_lines.append(line)
                print(f"📝 Added reason (no bullet): {line}")
            elif not line and reasoning_lines:
                # Empty line after reasons might indicate end of section
                break
    
    # Build reasoning text
    if reasoning_lines:
        reasoning = " • ".join(reasoning_lines[:3])  # Take top 3 reasons
    else:
        # Fallback: extract any meaningful lines that aren't verdict/reasons headers
        fallback_reasons = []
        for line in lines:
            clean_line = line.strip()
            if (clean_line and 
                not re.search(r'(?i)^\s*verdict', clean_line) and 
                not re.search(r'(?i)^\s*reasons', clean_line) and
                len(clean_line) > 10):
                fallback_reasons.append(clean_line)
        
        if fallback_reasons:
            reasoning = " • ".join(fallback_reasons[:2])
        else:
            reasoning = "Analysis completed but no specific reasons provided"
        print("⚠️ No structured reasons found, using fallback")
    
    # Calculate confidence based on analysis quality
    if len(reasoning_lines) >= 2:
        confidence = 0.85  # High confidence with multiple reasons
    elif len(reasoning_lines) >= 1:
        confidence = 0.70  # Medium confidence with at least one reason
    else:
        confidence = 0.55  # Low confidence with no specific reasons
    
    # Boost confidence for clear fake verdicts with reasons
    if prediction == 'fake' and len(reasoning_lines) >= 1:
        confidence = max(confidence, 0.80)
    
    print(f"🎯 Final: {prediction} with {confidence:.1%} confidence")
    
    # Extract red flags from reasoning
    red_flags = extract_red_flags_from_reasoning(reasoning)
    print(f"🚩 Red flags extracted: {red_flags}")
    
    return {
        'prediction': prediction,
        'confidence': confidence,
        'reasoning': reasoning,
        'red_flags': red_flags
    }

def extract_red_flags_from_reasoning(reasoning):
    """Extract red flags from the reasoning text"""
    red_flags = []
    reasoning_lower = reasoning.lower()
    
    flag_patterns = {
        'sensitive_info_request': ['ssn', 'social security', 'bank', 'personal information', 'sensitive information', 'send ssn'],
        'unrealistic_salary': ['high salary', 'unrealistic', 'extremely high', 'implausible', '$8000', '$9000', '$10000', 'too good to be true'],
        'personal_contact': ['gmail', 'yahoo', 'hotmail', 'personal email', '@gmail.com'],
        'urgency_tactics': ['urgent', 'immediately', 'quick start', 'asap', 'right away'],
        'no_qualifications': ['no experience', 'no skills', 'no qualifications', 'no background'],
        'upfront_payment': ['payment', 'fee', 'deposit', 'pay money', 'upfront'],
        'work_from_home_scam': ['work from home', 'remote work with high pay', 'data entry from home'],
        'vague_company': ['vague', 'no company', 'missing details', 'fraudulent', 'legitimate company'],
        'poor_grammar': ['poor grammar', 'spelling errors', 'unprofessional'],
        'money_transfer': ['money transfer', 'wire transfer', 'western union']
    }
    
    for flag_name, patterns in flag_patterns.items():
        if any(pattern in reasoning_lower for pattern in patterns):
            red_flags.append(flag_name)
    
    return red_flags

@app.route('/')
def home():
    return render_template_string(PROFESSIONAL_HTML)

@app.route('/analyze-status')
@cross_origin()
def analyze_status():
    """Check status of long-running analyses"""
    return jsonify({
        'active_analyses': len(long_running_analyses),
        'analyses': long_running_analyses
    })

@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/analyze', methods=['POST', 'OPTIONS'])
@cross_origin()
def analyze_job():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    print("🎯 ANALYZE ENDPOINT HIT!")
    print(f"📧 Headers: {dict(request.headers)}")
    print(f"🔍 Source: {request.json.get('source', 'unknown')}")
    
    job_text = request.json.get('job_text', '')
    
    if len(job_text) < 20:
        return jsonify({'error': 'Job description too short. Please provide more details.'})
    
    # Update statistics
    analysis_stats['total_analysis'] += 1
    
    try:
        start_time = time.time()
        
        print(f"🔍 Analyzing job text (length: {len(job_text)})")
        
        # Use the new RAG single model
        parsed_result = None
        try:
            # Add the scripts directory to Python path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            scripts_dir = os.path.join(current_dir, 'scripts')
            
            print(f"📁 Current directory: {current_dir}")
            print(f"📁 Scripts directory: {scripts_dir}")
            
            rag_script_path = os.path.join(scripts_dir, 'rag_single.py')
            print(f"📄 RAG script path: {rag_script_path}")
            print(f"✅ Script exists: {os.path.exists(rag_script_path)}")
            
            # Use subprocess to call the rag_single.py script
            print("🔄 Calling rag_single.py...")
            
            # Use the full job text for better analysis
            result = subprocess.run([
                'python3', rag_script_path,
                '--text', job_text
            ], capture_output=True, text=True, timeout=None, cwd=scripts_dir)
            
            print(f"📊 Subprocess return code: {result.returncode}")
            print(f"📄 STDOUT length: {len(result.stdout)}")
            print(f"📄 STDOUT preview: {result.stdout[:500]}...")
            print(f"❌ STDERR: {result.stderr}")
            
            if result.returncode == 0 and result.stdout.strip():
                print("✅ Successfully got output from rag_single.py")
                output = result.stdout.strip()
                parsed_result = parse_rag_single_output(output)
                parsed_result['method'] = 'RAG Single LLM'
            else:
                print("❌ rag_single.py failed or returned empty output")
                raise Exception(f"Script failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("⏰ rag_single.py timed out")
            parsed_result = simple_analysis(job_text)
            parsed_result['method'] = 'timeout_fallback'
            
        except Exception as e:
            print(f"❌ RAG single analysis failed: {e}")
            parsed_result = simple_analysis(job_text)
            parsed_result['method'] = 'error_fallback'
        
        # If we still don't have a result, use fallback
        if parsed_result is None:
            print("❌ No result from any method, using ultimate fallback")
            parsed_result = simple_analysis(job_text)
            parsed_result['method'] = 'ultimate_fallback'
        
        processing_time = time.time() - start_time
        analysis_stats['total_analysis_time'] += processing_time
        
        print(f"📊 Final result: {parsed_result['prediction']} with {parsed_result['confidence']:.1%} confidence")
        print(f"🔧 Method: {parsed_result.get('method', 'unknown')}")
        print(f"⏱️ Processing time: {processing_time:.1f}s")
        
        # Update scam detection count
        if parsed_result['prediction'] == 'fake':
            analysis_stats['scams_detected'] += 1
            
        # Track common patterns
        for flag in parsed_result.get('red_flags', []):
            analysis_stats['common_patterns'][flag] = analysis_stats['common_patterns'].get(flag, 0) + 1
            
        return jsonify({
            'prediction': parsed_result['prediction'],
            'confidence': float(parsed_result['confidence']),
            'reasoning': parsed_result.get('reasoning', 'No reasoning provided'),
            'red_flags': parsed_result.get('red_flags', []),
            'analysis_time': round(processing_time, 2),
            'method': parsed_result.get('method', 'unknown')
        })
        
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'})

@app.route('/analyze-batch', methods=['POST'])
@cross_origin()
def analyze_batch_jobs():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read CSV file
        df = pd.read_csv(file)
        
        # Create results dataframe
        results = []
        for index, row in df.iterrows():
            job_text = f"TITLE: {row.get('job_title', '')} | COMPANY: {row.get('company', '')} | DESCRIPTION: {row.get('description', '')} | REQUIREMENTS: {row.get('requirements', '')}"
            
            # Simple analysis for batch processing
            is_scam = any(indicator in job_text.lower() for indicator in 
                         ['ssn', 'social security', '$5000', '$8000', '$10000', '@gmail.com', '@yahoo.com', 'no experience', 'immediately'])
            
            results.append({
                'job_title': row.get('job_title', ''),
                'company': row.get('company', ''),
                'prediction': 'fake' if is_scam else 'real',
                'confidence': 0.8 if is_scam else 0.6,
                'risk_level': 'High' if is_scam else 'Low'
            })
        
        # Create output CSV
        output = io.StringIO()
        results_df = pd.DataFrame(results)
        results_df.to_csv(output, index=False)
        
        # Save submission record
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_df.to_csv(f'results/batch_analysis_{timestamp}.csv', index=False)
        
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'job_analysis_results_{timestamp}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500

@app.route('/stats')
@cross_origin()
def get_stats():
    avg_time = analysis_stats['total_analysis_time'] / max(analysis_stats['total_analysis'], 1)
    accuracy_rate = (analysis_stats['scams_detected'] / max(analysis_stats['total_analysis'], 1)) * 100
    
    # Get top common patterns
    common_patterns = sorted(
        [{'pattern': k, 'count': v} for k, v in analysis_stats['common_patterns'].items()],
        key=lambda x: x['count'],
        reverse=True
    )[:5]
    
    return jsonify({
        'total_analysis': analysis_stats['total_analysis'],
        'scams_detected': analysis_stats['scams_detected'],
        'accuracy_rate': round(accuracy_rate, 1),
        'avg_analysis_time': round(avg_time, 2),
        'common_patterns': common_patterns
    })

@app.route('/api/analyze', methods=['POST'])
@cross_origin()
def api_analyze():
    """API endpoint for programmatic access"""
    data = request.json
    job_text = data.get('job_text', '')
    model = data.get('model', 'improved_rag')
    
    if not job_text:
        return jsonify({'error': 'job_text is required'}), 400
    
    # Call the analysis function
    return analyze_job()

if __name__ == '__main__':
    print("🚀 Starting JobTrust AI - Professional Job Scam Detector")
    print("📍 Access the application at: http://localhost:5001")
    print("📊 Features:")
    print("   • Single job analysis with detailed reports")
    print("   • Batch CSV processing")
    print("   • REST API for developers")
    print("   • Real-time statistics")
    print("   • Professional user interface")
    print("\nPress Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5001)
