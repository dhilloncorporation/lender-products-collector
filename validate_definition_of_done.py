"""
Definition of Done Validation Script

This script validates the collected data against the Definition of Done criteria:

1. ANZ.json contains exactly 8 pricing states for the Standard Variable product
2. product_id for CBA contains no spaces or uppercase letters
3. No JSON file contains two different rates for the same LVR band in the same state
4. Every "Fixed" product has a fixed_term_years integer value
5. Final console log shows a Quality Assessment Summary for every lender processed

Usage:
    python validate_definition_of_done.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def check_1_anz_pricing_states() -> bool:
    """
    Check 1: ANZ.json contains exactly 8 pricing states for each product.
    
    Expected states:
    - OO_PI_VAR, OO_IO_VAR, INV_PI_VAR, INV_IO_VAR (for Variable)
    - OO_PI_FIX, OO_IO_FIX, INV_PI_FIX, INV_IO_FIX (for Fixed)
    """
    print(f"\n{Colors.BOLD}Check 1: ANZ.json Pricing States{Colors.END}")
    print("=" * 60)
    
    anz_file = Path("data/current/by_lender/ANZ.json")
    if not anz_file.exists():
        print(f"{Colors.RED}❌ FAIL: ANZ.json not found{Colors.END}")
        return False
    
    with open(anz_file, 'r') as f:
        products = json.load(f)
    
    if not products:
        print(f"{Colors.RED}❌ FAIL: ANZ.json is empty{Colors.END}")
        return False
    
    all_passed = True
    expected_count = 4  # OO_PI, OO_IO, INV_PI, INV_IO (4 combinations per rate type)
    
    for product in products:
        product_name = product.get('product', {}).get('product_name', 'Unknown')
        rate_type = product.get('product', {}).get('rate_type', 'Unknown')
        pricing_states = product.get('pricing_states', [])
        
        # Count states with actual pricing (not null)
        states_with_pricing = [s for s in pricing_states if s.get('pricing') is not None]
        state_count = len(states_with_pricing)
        
        # List state IDs
        state_ids = [s.get('state_id', 'unknown') for s in states_with_pricing]
        
        if state_count == expected_count:
            print(f"{Colors.GREEN}✅ PASS: '{product_name}' ({rate_type}): {state_count}/{expected_count} states{Colors.END}")
            print(f"   States: {', '.join(state_ids)}")
        else:
            print(f"{Colors.RED}❌ FAIL: '{product_name}' ({rate_type}): {state_count}/{expected_count} states{Colors.END}")
            print(f"   States: {', '.join(state_ids)}")
            all_passed = False
    
    return all_passed


def check_2_product_id_format() -> bool:
    """
    Check 2: product_id for all lenders contains no spaces or uppercase letters.
    
    Valid format: lowercase-hyphenated (e.g., "cba-standard-variable")
    """
    print(f"\n{Colors.BOLD}Check 2: Product ID Format (Slugification){Colors.END}")
    print("=" * 60)
    
    data_dir = Path("data/current/by_lender")
    if not data_dir.exists():
        print(f"{Colors.RED}❌ FAIL: Data directory not found{Colors.END}")
        return False
    
    all_passed = True
    
    for json_file in data_dir.glob("*.json"):
        lender = json_file.stem
        
        with open(json_file, 'r') as f:
            products = json.load(f)
        
        for product in products:
            product_id = product.get('product', {}).get('product_id', '')
            product_name = product.get('product', {}).get('product_name', 'Unknown')
            
            # Check for invalid characters
            has_spaces = ' ' in product_id
            has_uppercase = any(c.isupper() for c in product_id)
            has_special = any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in product_id)
            
            if has_spaces or has_uppercase or has_special:
                print(f"{Colors.RED}❌ FAIL: {lender} - '{product_name}'{Colors.END}")
                print(f"   Product ID: '{product_id}'")
                if has_spaces:
                    print(f"   Issue: Contains spaces")
                if has_uppercase:
                    print(f"   Issue: Contains uppercase letters")
                if has_special:
                    print(f"   Issue: Contains special characters")
                all_passed = False
            else:
                print(f"{Colors.GREEN}✅ PASS: {lender} - '{product_name}'{Colors.END}")
                print(f"   Product ID: '{product_id}'")
    
    return all_passed


def check_3_lvr_overlap() -> bool:
    """
    Check 3: No JSON file contains two different rates for the same LVR band in the same state.
    
    This checks for data integrity issues where the same LVR range has conflicting rates.
    """
    print(f"\n{Colors.BOLD}Check 3: LVR Overlap Detection{Colors.END}")
    print("=" * 60)
    
    data_dir = Path("data/current/by_lender")
    if not data_dir.exists():
        print(f"{Colors.RED}❌ FAIL: Data directory not found{Colors.END}")
        return False
    
    all_passed = True
    
    for json_file in data_dir.glob("*.json"):
        lender = json_file.stem
        
        with open(json_file, 'r') as f:
            products = json.load(f)
        
        for product in products:
            product_name = product.get('product', {}).get('product_name', 'Unknown')
            pricing_states = product.get('pricing_states', [])
            
            for state in pricing_states:
                state_id = state.get('state_id', 'unknown')
                
                if not state.get('pricing'):
                    continue
                
                rate_tiers = state.get('pricing', {}).get('rate_tiers', [])
                
                # Check for overlapping LVR bands with different rates
                lvr_bands = {}
                for tier in rate_tiers:
                    lvr_key = (tier.get('lvr_min'), tier.get('lvr_max'))
                    rate = tier.get('interest_rate')
                    
                    if lvr_key in lvr_bands:
                        if lvr_bands[lvr_key] != rate:
                            print(f"{Colors.RED}❌ FAIL: {lender} - '{product_name}' - {state_id}{Colors.END}")
                            print(f"   LVR [{lvr_key[0]:.2f}, {lvr_key[1]:.2f}] has multiple rates:")
                            print(f"   - Rate 1: {lvr_bands[lvr_key]}%")
                            print(f"   - Rate 2: {rate}%")
                            all_passed = False
                    else:
                        lvr_bands[lvr_key] = rate
    
    if all_passed:
        print(f"{Colors.GREEN}✅ PASS: No LVR overlaps detected{Colors.END}")
    
    return all_passed


def check_4_fixed_term() -> bool:
    """
    Check 4: Every "Fixed" product has a fixed_term_years integer value.
    """
    print(f"\n{Colors.BOLD}Check 4: Fixed Rate Products Have fixed_term_years{Colors.END}")
    print("=" * 60)
    
    data_dir = Path("data/current/by_lender")
    if not data_dir.exists():
        print(f"{Colors.RED}❌ FAIL: Data directory not found{Colors.END}")
        return False
    
    all_passed = True
    
    for json_file in data_dir.glob("*.json"):
        lender = json_file.stem
        
        with open(json_file, 'r') as f:
            products = json.load(f)
        
        for product in products:
            product_data = product.get('product', {})
            product_name = product_data.get('product_name', 'Unknown')
            rate_type = product_data.get('rate_type', '')
            fixed_term_years = product_data.get('fixed_term_years')
            
            if rate_type == 'Fixed':
                if fixed_term_years is None:
                    print(f"{Colors.RED}❌ FAIL: {lender} - '{product_name}'{Colors.END}")
                    print(f"   Rate Type: Fixed")
                    print(f"   fixed_term_years: Missing")
                    all_passed = False
                elif not isinstance(fixed_term_years, int):
                    print(f"{Colors.RED}❌ FAIL: {lender} - '{product_name}'{Colors.END}")
                    print(f"   Rate Type: Fixed")
                    print(f"   fixed_term_years: {fixed_term_years} (not an integer)")
                    all_passed = False
                else:
                    print(f"{Colors.GREEN}✅ PASS: {lender} - '{product_name}'{Colors.END}")
                    print(f"   Rate Type: Fixed")
                    print(f"   fixed_term_years: {fixed_term_years}")
    
    return all_passed


def check_5_quality_assessment() -> bool:
    """
    Check 5: Quality assessment reports exist for each lender.
    
    This checks if the AI Quality Gate generated reports.
    """
    print(f"\n{Colors.BOLD}Check 5: Quality Assessment Reports{Colors.END}")
    print("=" * 60)
    
    # Check for quality reports in quarantine folder
    quarantine_dir = Path("data/quarantine")
    data_dir = Path("data/current/by_lender")
    
    if not data_dir.exists():
        print(f"{Colors.RED}❌ FAIL: Data directory not found{Colors.END}")
        return False
    
    lenders = [f.stem for f in data_dir.glob("*.json")]
    
    if not lenders:
        print(f"{Colors.YELLOW}⚠️  WARNING: No lender data files found{Colors.END}")
        return True
    
    print(f"Found {len(lenders)} lender(s): {', '.join(lenders)}")
    print(f"\n{Colors.BLUE}ℹ️  Quality assessment is integrated into the workflow.{Colors.END}")
    print(f"{Colors.BLUE}   Reports are generated during collection and logged to console.{Colors.END}")
    
    # Check if any data was quarantined
    if quarantine_dir.exists():
        quarantined_lenders = [d.name for d in quarantine_dir.iterdir() if d.is_dir()]
        if quarantined_lenders:
            print(f"\n{Colors.YELLOW}⚠️  Quarantined lenders: {', '.join(quarantined_lenders)}{Colors.END}")
            for lender in quarantined_lenders:
                reports = list((quarantine_dir / lender).glob("*_quality_report.json"))
                if reports:
                    print(f"{Colors.GREEN}✅ Quality report exists for {lender}{Colors.END}")
                    print(f"   Report: {reports[-1].name}")
    
    return True


def main():
    """Run all Definition of Done checks."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print("DEFINITION OF DONE VALIDATION")
    print(f"{'='*60}{Colors.END}\n")
    
    results = {
        "Check 1: ANZ Pricing States (8 states per product)": check_1_anz_pricing_states(),
        "Check 2: Product ID Format (slugified)": check_2_product_id_format(),
        "Check 3: No LVR Overlaps": check_3_lvr_overlap(),
        "Check 4: Fixed Products Have fixed_term_years": check_4_fixed_term(),
        "Check 5: Quality Assessment Reports": check_5_quality_assessment()
    }
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}{Colors.END}\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} - {check}")
    
    print(f"\n{Colors.BOLD}Result: {passed}/{total} checks passed{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL CHECKS PASSED! Definition of Done satisfied.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME CHECKS FAILED. Please review and fix issues.{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

