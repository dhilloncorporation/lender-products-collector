"""
Result Verification Agent - AI Quality Gate

ROLE: Quality Assurance Agent (LLM-powered)
PURPOSE: Audits collected products against BIAN schema and business rules

This agent implements the "AI Quality Gate" that runs AFTER data collection
to ensure data quality and completeness. It uses LLM-based intelligence to:

1. Validate schema compliance
2. Calculate confidence scores (0-100)
3. Detect missing information
4. Identify data quality issues
5. Generate quality assessment reports
6. Quarantine low-quality results

CONFIDENCE SCORING PENALTIES:
- -40 pts: Overlapping LVR tiers in same state (different rates for same LVR)
- -20 pts: Missing "Interest Only" or "Investment" surfaces
- -20 pts: Fixed Rate product missing fixed_term_months
- -10 pts: Missing comparison rates
- -10 pts: Missing product features

QUARANTINE THRESHOLD:
- Score < 40: Data is flagged as "quarantined" and requires manual review

DEPENDENCIES:
- LangChain OpenAI (for LLM-based validation)
- Pydantic models (BIAN schema validation)

USAGE:
    verifier = ResultVerificationAgent()
    result = await verifier.verify_collection_result(
        lender_name="ANZ",
        products=collected_products,
        collection_metadata=metadata
    )
    
    if result.confidence_score < 40:
        # Handle quarantine
        logger.warning(f"Collection quarantined: {result.issues}")
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    ChatOpenAI = None

logger = logging.getLogger(__name__)


class QualityIssue(BaseModel):
    """Single quality issue identified during verification."""
    severity: str = Field(..., description="Severity: critical, warning, info")
    category: str = Field(..., description="Category: schema, data_integrity, completeness")
    message: str = Field(..., description="Human-readable issue description")
    affected_product_ids: List[str] = Field(default_factory=list, description="Product IDs affected")
    penalty_points: int = Field(default=0, description="Confidence score penalty")


class VerificationResult(BaseModel):
    """Result of verification process."""
    lender_name: str = Field(..., description="Lender name")
    timestamp: datetime = Field(default_factory=datetime.now, description="Verification timestamp")
    
    # Scores
    confidence_score: int = Field(..., description="Overall confidence score (0-100)", ge=0, le=100)
    completeness_score: int = Field(..., description="Data completeness (0-100)", ge=0, le=100)
    consistency_score: int = Field(..., description="Data consistency (0-100)", ge=0, le=100)
    
    # Issues
    issues: List[QualityIssue] = Field(default_factory=list, description="Identified issues")
    
    # Status
    status: str = Field(..., description="Status: passed, quarantined, failed")
    quarantined: bool = Field(default=False, description="Whether data is quarantined")
    
    # Missing information
    missing_states: List[str] = Field(default_factory=list, description="Missing pricing states")
    missing_fields: Dict[str, List[str]] = Field(default_factory=dict, description="Missing fields by product")
    
    # Summary
    total_products: int = Field(default=0, description="Total products collected")
    products_with_issues: int = Field(default=0, description="Products with quality issues")
    
    # AI Analysis (optional)
    ai_analysis: Optional[str] = Field(None, description="LLM-generated analysis")


class ResultVerificationAgent:
    """
    AI Quality Gate agent for verifying collected product data.
    
    This agent audits collected data against BIAN schema and business rules,
    calculates confidence scores, and identifies quality issues.
    
    Attributes:
        llm: Language model for intelligent analysis
        use_ai: Whether to use AI-powered validation
    """
    
    def __init__(self, use_ai: bool = True):
        """
        Initialize verification agent.
        
        Args:
            use_ai: Whether to use AI-powered validation (requires OpenAI API key)
        """
        self.use_ai = use_ai and HAS_OPENAI
        
        if self.use_ai:
            try:
                self.llm = ChatOpenAI(model="gpt-4", temperature=0)
                logger.info("✅ AI Quality Gate enabled (GPT-4)")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize OpenAI: {e}. Falling back to rule-based validation.")
                self.use_ai = False
                self.llm = None
        else:
            self.llm = None
            logger.info("ℹ️  AI Quality Gate disabled (rule-based validation only)")
    
    async def verify_collection_result(
        self,
        lender_name: str,
        products: List[Dict[str, Any]],
        collection_metadata: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Verify collected products and generate quality assessment.
        
        Args:
            lender_name: Lender name
            products: List of collected products (v2.0.0 format)
            collection_metadata: Optional metadata about collection process
            
        Returns:
            VerificationResult with scores, issues, and recommendations
        """
        logger.info(f"🔍 Starting quality verification for {lender_name}...")
        
        issues = []
        missing_states = []
        missing_fields = {}
        
        # Start with perfect score
        confidence_score = 100
        completeness_score = 100
        consistency_score = 100
        
        # === VALIDATION CHECKS ===
        
        # Check 1: Product ID format (must be slugified)
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            product_name = product.get('product', {}).get('product_name', '')
            
            # Check if product_id is properly slugified
            if not self._is_valid_slug(product_id):
                issues.append(QualityIssue(
                    severity="critical",
                    category="schema",
                    message=f"Product ID '{product_id}' is not properly slugified (must be lowercase-hyphenated)",
                    affected_product_ids=[product_id],
                    penalty_points=10
                ))
                confidence_score -= 10
        
        # Check 2: LVR Overlap Detection (CRITICAL)
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            pricing_states = product.get('pricing_states', [])
            
            for state in pricing_states:
                state_id = state.get('state_id', '')
                rate_tiers = state.get('pricing', {}).get('rate_tiers', []) if state.get('pricing') else []
                
                # Check for overlapping LVR tiers with different rates
                lvr_bands = {}
                for tier in rate_tiers:
                    lvr_key = (tier.get('lvr_min'), tier.get('lvr_max'))
                    rate = tier.get('interest_rate')
                    
                    if lvr_key in lvr_bands:
                        if lvr_bands[lvr_key] != rate:
                            issues.append(QualityIssue(
                                severity="critical",
                                category="data_integrity",
                                message=f"LVR overlap in {state_id}: LVR [{lvr_key[0]:.2f}, {lvr_key[1]:.2f}] has multiple rates ({lvr_bands[lvr_key]}% vs {rate}%)",
                                affected_product_ids=[product_id],
                                penalty_points=40
                            ))
                            confidence_score -= 40
                    else:
                        lvr_bands[lvr_key] = rate
        
        # Check 3: Missing Pricing States (Investment, Interest Only)
        expected_state_types = {
            'OwnerOccupied_PrincipalAndInterest',
            'OwnerOccupied_InterestOnly',
            'Investment_PrincipalAndInterest',
            'Investment_InterestOnly'
        }
        
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            pricing_states = product.get('pricing_states', [])
            
            # Get captured states
            captured_states = set()
            for state in pricing_states:
                if state.get('pricing') is not None:  # Only count states with actual pricing
                    params = state.get('state_parameters', {})
                    loan_type = params.get('loan_type', '')
                    repayment_type = params.get('repayment_type', '')
                    captured_states.add(f"{loan_type}_{repayment_type}")
            
            # Check for missing critical states
            missing = expected_state_types - captured_states
            if missing:
                # Separate missing types
                missing_loan_types = set()
                missing_repayment_types = set()
                
                for m in missing:
                    if 'Investment' in m:
                        missing_loan_types.add('Investment')
                    if 'InterestOnly' in m:
                        missing_repayment_types.add('InterestOnly')
                
                penalty = 0
                if missing_loan_types:
                    issues.append(QualityIssue(
                        severity="warning",
                        category="completeness",
                        message=f"Missing Investment loan surfaces for '{product.get('product', {}).get('product_name', '')}'",
                        affected_product_ids=[product_id],
                        penalty_points=20
                    ))
                    missing_states.extend(list(missing_loan_types))
                    penalty += 20
                
                if missing_repayment_types:
                    issues.append(QualityIssue(
                        severity="warning",
                        category="completeness",
                        message=f"Missing Interest Only repayment surfaces for '{product.get('product', {}).get('product_name', '')}'",
                        affected_product_ids=[product_id],
                        penalty_points=20
                    ))
                    missing_states.extend(list(missing_repayment_types))
                    penalty += 20
                
                completeness_score -= penalty
                confidence_score -= penalty
        
        # Check 4: Fixed Rate Products Missing fixed_term_months (CRITICAL)
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            product_data = product.get('product', {})
            rate_type = product_data.get('rate_type', '')
            fixed_term_years = product_data.get('fixed_term_years')
            
            if rate_type == 'Fixed' and not fixed_term_years:
                issues.append(QualityIssue(
                    severity="critical",
                    category="completeness",
                    message=f"Fixed rate product '{product_data.get('product_name', '')}' missing fixed_term_years",
                    affected_product_ids=[product_id],
                    penalty_points=20
                ))
                
                if product_id not in missing_fields:
                    missing_fields[product_id] = []
                missing_fields[product_id].append('fixed_term_years')
                
                completeness_score -= 20
                confidence_score -= 20
        
        # Check 5: Missing Comparison Rates
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            pricing_states = product.get('pricing_states', [])
            
            for state in pricing_states:
                if not state.get('pricing'):
                    continue
                    
                rate_tiers = state.get('pricing', {}).get('rate_tiers', [])
                for tier in rate_tiers:
                    if not tier.get('comparison_rate') or tier.get('comparison_rate') == 0:
                        issues.append(QualityIssue(
                            severity="warning",
                            category="completeness",
                            message=f"Missing comparison rate in {state.get('state_id', 'unknown state')}",
                            affected_product_ids=[product_id],
                            penalty_points=10
                        ))
                        
                        if product_id not in missing_fields:
                            missing_fields[product_id] = []
                        if 'comparison_rate' not in missing_fields[product_id]:
                            missing_fields[product_id].append('comparison_rate')
                        
                        completeness_score -= 10
                        confidence_score -= 10
                        break  # Only penalize once per state
        
        # Check 6: Minimum Data Requirements
        if len(products) == 0:
            issues.append(QualityIssue(
                severity="critical",
                category="completeness",
                message="No products collected",
                affected_product_ids=[],
                penalty_points=100
            ))
            confidence_score = 0
            completeness_score = 0
        
        # === AI-POWERED ANALYSIS (Optional) ===
        ai_analysis = None
        if self.use_ai and self.llm and len(products) > 0:
            try:
                ai_analysis = await self._run_ai_analysis(lender_name, products, issues)
            except Exception as e:
                logger.warning(f"⚠️  AI analysis failed: {e}")
        
        # === CALCULATE FINAL SCORES ===
        
        # Ensure scores don't go negative
        confidence_score = max(0, confidence_score)
        completeness_score = max(0, completeness_score)
        consistency_score = max(0, consistency_score)
        
        # Determine status
        if confidence_score < 40:
            status = "quarantined"
            quarantined = True
        elif confidence_score < 70:
            status = "warning"
            quarantined = False
        else:
            status = "passed"
            quarantined = False
        
        # Count products with issues
        affected_ids = set()
        for issue in issues:
            affected_ids.update(issue.affected_product_ids)
        
        # Build result
        result = VerificationResult(
            lender_name=lender_name,
            confidence_score=confidence_score,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            issues=issues,
            status=status,
            quarantined=quarantined,
            missing_states=list(set(missing_states)),
            missing_fields=missing_fields,
            total_products=len(products),
            products_with_issues=len(affected_ids),
            ai_analysis=ai_analysis
        )
        
        # Log summary
        logger.info(f"✅ Verification complete for {lender_name}:")
        logger.info(f"   Confidence Score: {confidence_score}/100")
        logger.info(f"   Completeness Score: {completeness_score}/100")
        logger.info(f"   Status: {status.upper()}")
        logger.info(f"   Issues: {len(issues)} ({len([i for i in issues if i.severity == 'critical'])} critical)")
        
        if quarantined:
            logger.warning(f"   ⚠️  DATA QUARANTINED - Manual review required!")
        
        return result
    
    def _is_valid_slug(self, text: str) -> bool:
        """Check if text is a valid slug (lowercase, alphanumeric + hyphens)."""
        if not text:
            return False
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', text))
    
    async def _run_ai_analysis(
        self,
        lender_name: str,
        products: List[Dict[str, Any]],
        issues: List[QualityIssue]
    ) -> str:
        """
        Run AI-powered analysis of collected data.
        
        Args:
            lender_name: Lender name
            products: Collected products
            issues: Issues identified by rule-based validation
            
        Returns:
            AI-generated analysis text
        """
        # Prepare summary for LLM
        summary = {
            "lender": lender_name,
            "total_products": len(products),
            "product_names": [p.get('product', {}).get('product_name', '') for p in products[:5]],  # First 5
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message
                }
                for i in issues[:10]  # First 10 issues
            ]
        }
        
        system_prompt = """You are a financial data quality analyst. Your task is to review 
collected loan product data and provide a brief quality assessment.

Focus on:
1. Data completeness (are all expected fields present?)
2. Data consistency (do the values make sense?)
3. Business logic (do rates and terms align with industry standards?)
4. Potential data collection issues

Keep your analysis concise (2-3 sentences) and actionable."""
        
        user_prompt = f"""Analyze this collection result:

{summary}

Provide a brief quality assessment."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def generate_quality_report(self, result: VerificationResult) -> Dict[str, Any]:
        """
        Generate a detailed quality assessment report.
        
        Args:
            result: Verification result
            
        Returns:
            Dictionary suitable for JSON export
        """
        return {
            "lender": result.lender_name,
            "timestamp": result.timestamp.isoformat(),
            "scores": {
                "confidence": result.confidence_score,
                "completeness": result.completeness_score,
                "consistency": result.consistency_score
            },
            "status": result.status,
            "quarantined": result.quarantined,
            "summary": {
                "total_products": result.total_products,
                "products_with_issues": result.products_with_issues,
                "total_issues": len(result.issues),
                "critical_issues": len([i for i in result.issues if i.severity == "critical"]),
                "warnings": len([i for i in result.issues if i.severity == "warning"])
            },
            "missing_data": {
                "missing_states": result.missing_states,
                "missing_fields": result.missing_fields
            },
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "affected_products": i.affected_product_ids,
                    "penalty": i.penalty_points
                }
                for i in result.issues
            ],
            "ai_analysis": result.ai_analysis if result.ai_analysis else "Not available"
        }

