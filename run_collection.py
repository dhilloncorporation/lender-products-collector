"""
Main Entry Point for Loan Product Collection System

This module serves as the primary entry point for running the LangGraph-based
collection workflow. It orchestrates the entire loan product collection process
across all configured lenders.

Purpose:
    - Initialize configuration managers (settings and lenders)
    - Create and execute the CollectionWorkflow
    - Display collection results and statistics
    - Provide clear feedback on success/failure status

Workflow:
    1. Load environment variables from .env file
    2. Initialize YamlSettingsManager and LenderConfigManager
    3. Create CollectionWorkflow instance
    4. Execute workflow with recursion limit configuration
    5. Display results summary (success/failure counts, errors, product counts)

Dependencies:
    - load_env: Custom module for loading .env file
    - CollectionWorkflow: Main LangGraph workflow orchestrator
    - YamlSettingsManager: Manages collection settings from YAML
    - LenderConfigManager: Manages lender configurations

Environment Variables:
    - OPENAI_API_KEY: Required for LLM features (if used)
    - CUSTOM_SEARCH_API_KEY: Optional, for Google Custom Search
    - CUSTOM_SEARCH_CX: Optional, for Google Custom Search Engine ID
    - OPENAI_MODEL: Optional, defaults to gpt-4o-mini

Output:
    - Collected products: data/current/by_lender/{LENDER}.json
    - Collection index: data/index.json
    - Snapshots: data/snapshots/parsed/{LENDER}/

Usage:
    Basic execution:
        python run_collection.py

    The script will:
        - Load configuration from src/configs/collection_settings.yaml
        - Load lenders from src/configs/lenders.json
        - Run collection workflow for all configured lenders
        - Display results and save data to data/ directory

Example Output:
    Starting Loan Product Collection System
    ================================================================================
    Starting collection workflow...
    ================================================================================
    Collection Complete!
    Total Lenders: 15
    Successful: 12
    Failed: 3
    
    Collection Results:
      CBA: success - 5 products
      ANZ: success - 3 products
      ...

See Also:
    - src/agents/workflows/collection_workflow.py: Workflow implementation
    - src/configs/settings_manager.py: Settings management
    - src/configs/lender_config.py: Lender configuration
    - project-docs/ENV_SETUP.md: Environment setup guide
"""

import asyncio
import logging
import argparse
from typing import Dict, Any

# Load .env file (simple approach)
import load_env

from src.agents.workflows.collection_workflow import CollectionWorkflow
from src.configs.settings_manager import YamlSettingsManager
from src.configs.lender_config import LenderConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Concurrency settings
# Set to 3 for laptops, 5-10 for powerful servers/cloud
DEFAULT_CONCURRENCY = 3


async def main():
    """
    Execute the loan product collection workflow.
    
    This function:
        1. Initializes configuration managers
        2. Creates the CollectionWorkflow instance
        3. Runs the collection process for all configured lenders
        4. Displays comprehensive results including:
           - Total lenders processed
           - Success/failure counts
           - Error messages (if any)
           - Product counts per lender
    
    Returns:
        None (results are logged and saved to data/ directory)
    
    Raises:
        Exception: If workflow initialization or execution fails
        
    Note:
        The recursion_limit is set to 50 to accommodate 15 lenders plus
        workflow overhead. Adjust if processing more lenders.
    """
    logger.info("Starting Loan Product Collection System")
    logger.info("="*80)
    
    # Initialize configuration managers
    settings_manager = YamlSettingsManager()
    lender_config_manager = LenderConfigManager()
    
    # Create workflow
    workflow = CollectionWorkflow(settings_manager, lender_config_manager)
    
    # Run collection with increased recursion limit (15 lenders + workflow overhead)
    logger.info("Starting collection workflow...")
    config = {"recursion_limit": 50}
    final_state = await workflow.run_collection(config=config)
    
    # Print results
    logger.info("="*80)
    logger.info("Collection Complete!")
    logger.info(f"Total Lenders: {final_state['total_lenders']}")
    logger.info(f"Successful: {final_state['success_count']}")
    logger.info(f"Failed: {final_state['failure_count']}")
    
    if final_state['errors']:
        logger.warning("\nErrors encountered:")
        for error in final_state['errors']:
            logger.warning(f"  - {error}")
    
    logger.info("\nCollection Results:")
    for lender, result in final_state['collection_results'].items():
        status = result.get('status', 'unknown')
        count = result.get('count', 0)
        logger.info(f"  {lender}: {status} - {count} products")
    
    logger.info("="*80)
    logger.info("Check data/current/by_lender/ for collected products")
    logger.info("Check data/index.json for collection catalog")


if __name__ == "__main__":
    asyncio.run(main())
