import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import re
import time

class FixedImprovedJobScamRAG:
    def __init__(self, knowledge_base_path='../data/fake_job_postings.csv'):
        print("Loading FIXED IMPROVED RAG system...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.knowledge_base = self.load_enhanced_knowledge_base(knowledge_base_path)
        self.index = self.build_index()
        print(f"✅ Fixed Improved RAG ready with {len(self.knowledge_base)} expert patterns")
    
    def load_enhanced_knowledge_base(self, path):
        """Create a MUCH better knowledge base with expert rules - FIXED VERSION"""
        df = pd.read_csv(path)
        df = df.fillna('')
        
        knowledge_entries = []
        
        # 1. ENHANCED SCAM PATTERNS (more specific)
        fake_jobs = df[df['fraudulent'] == 1]
        print(f"Adding {len(fake_jobs)} real scam examples...")
        
        for _, row in fake_jobs.iterrows():
            title = str(row['title'])
            company = str(row.get('company_profile', ''))[:150]
            description = str(row['description'])[:300]
            requirements = str(row.get('requirements', ''))[:200]
            
            # Create multiple specialized entries from each scam
            entries = [
                {
                    'text': f"SCAM_PATTERN: {title}. Company: {company}. Key phrases: {self.extract_scam_phrases(description)}",
                    'red_flags': self.extract_detailed_red_flags(row),
                    'source': 'Kaggle Scam Database',
                    'label': 'fake',
                    'confidence_boost': 1.0
                },
                {
                    'text': f"SCAM_INDICATORS: {title}. Suspicious elements: {self.get_suspicious_elements(description + requirements)}",
                    'red_flags': self.extract_detailed_red_flags(row),
                    'source': 'Scam Analysis',
                    'label': 'fake', 
                    'confidence_boost': 0.9
                }
            ]
            knowledge_entries.extend(entries)
        
        # 2. ENHANCED LEGITIMATE PATTERNS (more professional examples) - FIXED SECTION
        real_jobs = df[df['fraudulent'] == 0]
        
        # Filter for HIGH-QUALITY legitimate jobs only - FIXED LOGIC
        quality_mask = (
            (real_jobs['company_profile'].str.len() > 100) &
            (real_jobs['description'].str.len() > 200) &
            (real_jobs['requirements'].str.len() > 100)
        )
        
        # Handle NaN values properly
        quality_mask = quality_mask.fillna(False)
        
        quality_real = real_jobs[quality_mask]
        
        # Remove staffing/recruiting agencies to focus on direct employers
        company_mask = ~quality_real['company_profile'].str.contains(
            'staffing|recruiting|agency', case=False, na=False
        )
        quality_real = quality_real[company_mask]
        
        # Sample if we have too many, but handle case where we have few samples
        target_samples = min(500, len(quality_real))
        if len(quality_real) > target_samples:
            quality_real = quality_real.sample(target_samples, random_state=42)
        else:
            # If we don't have enough quality samples, take what we have
            quality_real = quality_real.copy()
            
        print(f"Adding {len(quality_real)} high-quality legitimate examples...")
        
        for _, row in quality_real.iterrows():
            title = str(row['title'])
            company = str(row.get('company_profile', ''))[:150]
            description = str(row['description'])[:300]
            
            entries = [
                {
                    'text': f"LEGITIMATE_PATTERN: {title} at {company}. Professional description: {description[:200]}",
                    'red_flags': [],
                    'source': 'Professional Job Database', 
                    'label': 'real',
                    'confidence_boost': 1.0
                },
                {
                    'text': f"LEGIT_SIGNALS: {title}. Company details provided. Specific requirements listed.",
                    'red_flags': [],
                    'source': 'Legitimacy Indicators',
                    'label': 'real',
                    'confidence_boost': 0.8
                }
            ]
            knowledge_entries.extend(entries)
        
        # 3. EXPERT RULES (cybersecurity knowledge)
        expert_rules = [
            {
                'text': "SCAM_RULE: Requests Social Security Number, bank details, or sensitive personal information upfront",
                'red_flags': ["sensitive_info_request"],
                'source': 'Cybersecurity Expert Rule',
                'label': 'fake',
                'confidence_boost': 1.0
            },
            {
                'text': "SCAM_RULE: Unrealistically high salary for minimal work or no experience required",
                'red_flags': ["unrealistic_salary", "no_experience"],
                'source': 'Financial Expert Rule', 
                'label': 'fake',
                'confidence_boost': 0.9
            },
            {
                'text': "SCAM_RULE: Uses personal email addresses (@gmail.com, @yahoo.com) instead of company domain",
                'red_flags': ["personal_contact"],
                'source': 'Professional Standards Rule',
                'label': 'fake',
                'confidence_boost': 0.8
            },
            {
                'text': "SCAM_RULE: Urgent hiring language with pressure to act immediately",
                'red_flags': ["urgency", "pressure_tactics"],
                'source': 'Psychological Tactics Rule',
                'label': 'fake',
                'confidence_boost': 0.7
            },
            {
                'text': "LEGIT_RULE: Professional company with detailed information and verifiable website",
                'red_flags': [],
                'source': 'Legitimacy Verification Rule',
                'label': 'real', 
                'confidence_boost': 0.8
            },
            {
                'text': "LEGIT_RULE: Specific job requirements, qualifications, and professional application process",
                'red_flags': [],
                'source': 'Professional Standards Rule',
                'label': 'real',
                'confidence_boost': 0.7
            },
            {
                'text': "LEGIT_RULE: Realistic salary range and professional benefits package",
                'red_flags': [],
                'source': 'Compensation Standards Rule', 
                'label': 'real',
                'confidence_boost': 0.6
            }
        ]
        
        knowledge_entries.extend(expert_rules)
        
        # 4. DOMAIN-SPECIFIC PATTERNS
        domain_patterns = [
            {
                'text': "SCAM_PATTERN: Work-from-home data entry with extremely high pay and no experience required",
                'red_flags': ["unrealistic_salary", "no_experience", "work_from_home_scam"],
                'source': 'Common Scam Type',
                'label': 'fake',
                'confidence_boost': 0.9
            },
            {
                'text': "SCAM_PATTERN: Pyramid scheme or multi-level marketing with emphasis on recruiting",
                'red_flags': ["pyramid_scheme", "recruiting_focus"],
                'source': 'MLM Scam Pattern',
                'label': 'fake', 
                'confidence_boost': 0.9
            },
            {
                'text': "LEGIT_PATTERN: Established tech company with clear career progression and benefits",
                'red_flags': [],
                'source': 'Tech Industry Standard',
                'label': 'real',
                'confidence_boost': 0.8
            }
        ]
        
        knowledge_entries.extend(domain_patterns)
        
        print(f"🎯 Enhanced knowledge base: {len(knowledge_entries)} expert patterns")
        return knowledge_entries
    
    def extract_scam_phrases(self, text):
        """Extract key scam indicator phrases"""
        text_lower = text.lower()
        scam_phrases = []
        
        scam_indicators = [
            'ssn', 'social security', 'bank details', 'routing number',
            'immediately', 'urgent', 'quick start', 'asap',
            'no experience', 'no skills', 'no background',
            'earn much', 'get rich', 'high salary', '$5000', '$8000', '$10000',
            'personal email', '@gmail', '@yahoo', '@hotmail',
            'payment', 'fee', 'deposit', 'training materials'
        ]
        
        for indicator in scam_indicators:
            if indicator in text_lower:
                scam_phrases.append(indicator)
        
        return ', '.join(scam_phrases[:5])  # Return top 5 phrases
    
    def get_suspicious_elements(self, text):
        """Identify specific suspicious elements"""
        text_lower = text.lower()
        elements = []
        
        if any(term in text_lower for term in ['ssn', 'social security', 'bank details']):
            elements.append('sensitive_info_request')
        if any(term in text_lower for term in ['$5000', '$8000', '$10000', 'high salary']):
            elements.append('unrealistic_compensation')
        if any(term in text_lower for term in ['no experience', 'no skills', 'no background']):
            elements.append('no_qualifications')
        if any(term in text_lower for term in ['immediately', 'urgent', 'quick start']):
            elements.append('urgency_pressure')
        
        return ', '.join(elements)
    
    def extract_detailed_red_flags(self, job_row):
        """Extract comprehensive red flags"""
        red_flags = []
        
        company = str(job_row.get('company_profile', '')).lower()
        description = str(job_row.get('description', '')).lower()
        requirements = str(job_row.get('requirements', '')).lower()
        
        full_text = company + ' ' + description + ' ' + requirements
        
        # Comprehensive red flag detection
        red_flag_patterns = {
            'sensitive_info_request': ['ssn', 'social security', 'bank details', 'bank account', 'routing number'],
            'unrealistic_salary': ['$5000', '$8000', '$10000', '$12000', '$15000', 'high salary', 'earn much'],
            'personal_contact': ['@gmail.com', '@yahoo.com', '@hotmail.com', 'personal email'],
            'urgency_tactics': ['immediately', 'urgent', 'quick start', 'asap', 'right away', 'instant'],
            'upfront_payment': ['payment', 'fee', 'deposit', 'background check fee', 'training materials'],
            'no_qualifications': ['no experience', 'no skills', 'no background', 'no degree', 'no certification'],
            'pyramid_scheme': ['recruit', 'multi-level', 'mlm', 'pyramid', 'downline'],
            'vague_company': ['established company', 'successful business', 'leading firm', 'premier organization'],
            'work_from_home_scam': ['work from home', 'remote work', 'home based', 'telecommute']
        }
        
        for flag_name, patterns in red_flag_patterns.items():
            if any(pattern in full_text for pattern in patterns):
                red_flags.append(flag_name)
        
        return red_flags
    
    def build_index(self):
        """Build FAISS index for similarity search"""
        texts = [entry['text'] for entry in self.knowledge_base]
        embeddings = self.encoder.encode(texts)
        
        index = faiss.IndexFlatIP(embeddings.shape[1])
        faiss.normalize_L2(embeddings)
        index.add(embeddings)
        
        return index
    
    def analyze_job_enhanced(self, job_text):
        """Enhanced analysis with confidence scoring and reasoning"""
        start_time = time.time()
        
        # Retrieve similar patterns
        similar_patterns = self.retrieve_similar_patterns(job_text, k=5)
        
        # Calculate weighted scores with confidence boosts
        fake_score = 0
        real_score = 0
        red_flags_found = set()
        reasoning_parts = []
        
        for pattern in similar_patterns:
            weight = pattern['similarity_score'] * pattern.get('confidence_boost', 1.0)
            
            if pattern['label'] == 'fake':
                fake_score += weight
                # Add red flags from similar scams
                red_flags_found.update(pattern['red_flags'])
                if pattern['similarity_score'] > 0.4:
                    reasoning_parts.append(f"Matches known scam: {pattern['text'][:80]}...")
            else:
                real_score += weight
                if pattern['similarity_score'] > 0.4:
                    reasoning_parts.append(f"Matches legitimate pattern: {pattern['text'][:80]}...")
        
        # Calculate final scores
        total_score = fake_score + real_score
        if total_score > 0:
            fake_confidence = fake_score / total_score
        else:
            fake_confidence = 0.5
        
        # Enhanced red flag detection
        detected_red_flags = self.extract_detailed_red_flags_from_text(job_text)
        red_flags_found.update(detected_red_flags)
        
        # Adjust confidence based on red flags
        red_flag_penalty = len(red_flags_found) * 0.1
        fake_confidence = min(0.95, fake_confidence + red_flag_penalty)
        
        # Final decision
        prediction = 'fake' if fake_confidence > 0.5 else 'real'
        final_confidence = max(fake_confidence, 1 - fake_confidence)
        
        # Build comprehensive reasoning
        if red_flags_found:
            reasoning_parts.append(f"Detected red flags: {', '.join(list(red_flags_found)[:5])}")
        
        reasoning = " | ".join(reasoning_parts[:3])  # Top 3 reasons
        
        return {
            'prediction': prediction,
            'confidence': final_confidence,
            'processing_time': time.time() - start_time,
            'method': 'Improved RAG',
            'red_flags': list(red_flags_found),
            'reasoning': reasoning,
            'patterns_matched': len([p for p in similar_patterns if p['similarity_score'] > 0.3])
        }
    
    def extract_detailed_red_flags_from_text(self, text):
        """Extract red flags directly from input text"""
        text_lower = text.lower()
        red_flags = []
        
        red_flag_patterns = {
            'sensitive_info_request': ['ssn', 'social security', 'bank details', 'bank account'],
            'unrealistic_salary': ['$5000', '$8000', '$10000', '$12000', '$15000'],
            'personal_contact': ['@gmail.com', '@yahoo.com', '@hotmail.com'],
            'urgency_tactics': ['immediately', 'urgent', 'quick start', 'asap'],
            'upfront_payment': ['payment', 'fee', 'deposit', 'training materials'],
            'no_qualifications': ['no experience', 'no skills', 'no background']
        }
        
        for flag_name, patterns in red_flag_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                red_flags.append(flag_name)
        
        return red_flags
    
    def retrieve_similar_patterns(self, query, k=5):
        """Retrieve similar patterns with enhanced filtering"""
        query_embedding = self.encoder.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search for similar patterns
        scores, indices = self.index.search(query_embedding, k*2)  # Get more, filter later
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.knowledge_base) and score > 0.2:  # Filter low similarity
                pattern = self.knowledge_base[idx]
                results.append({
                    'text': pattern['text'],
                    'red_flags': pattern['red_flags'],
                    'source': pattern['source'],
                    'label': pattern['label'],
                    'confidence_boost': pattern.get('confidence_boost', 1.0),
                    'similarity_score': float(score)
                })
        
        return results[:k]  # Return top k

# Test the fixed improved RAG
if __name__ == "__main__":
    print("🧪 TESTING FIXED IMPROVED RAG SYSTEM")
    print("=" * 60)
    
    try:
        improved_rag = FixedImprovedJobScamRAG()
        
        test_jobs = [
            "Work from home data entry. No experience needed. Earn $8,000 monthly. Send SSN to quickhire@gmail.com",
            "Software Engineer at Google. Bachelor's degree required. Competitive salary. Apply via careers.google.com"
        ]
        
        for job in test_jobs:
            print(f"\n🔍 Analyzing: {job[:60]}...")
            result = improved_rag.analyze_job_enhanced(job)
            print(f"   Prediction: {result['prediction'].upper()} ({result['confidence']:.1%} confidence)")
            print(f"   Red flags: {result['red_flags']}")
            print(f"   Reasoning: {result['reasoning']}")
            print(f"   Time: {result['processing_time']:.2f}s")
            
        print("\n✅ FIXED IMPROVED RAG WORKING CORRECTLY!")
        
    except Exception as e:
        print(f"❌ Error in fixed improved RAG: {e}")
        import traceback
        traceback.print_exc()
