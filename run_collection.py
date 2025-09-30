"""Run the LangGraph collection workflow."""

import asyncio
import logging
from src.agents.workflows.collection_workflow import CollectionWorkflow
from src.configs.settings_manager import SettingsManager
from src.configs.lender_config import LenderConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Run the collection workflow."""
    logger.info("Starting Loan Product Collection System")
    logger.info("="*80)
    
    # Initialize configuration managers
    settings_manager = SettingsManager()
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
