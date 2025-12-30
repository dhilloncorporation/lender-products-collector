"""Test ANZ collection only."""
import asyncio
import os
from pathlib import Path

# Change to script directory
os.chdir(Path(__file__).parent)

from src.agents.workflows.collection_workflow import CollectionWorkflow
from src.configs.settings_manager import YamlSettingsManager
from src.configs.lender_config import LenderConfig


async def test_anz():
    """Test ANZ collection with enhanced filter detection."""
    
    # Load settings
    settings_manager = YamlSettingsManager()
    lender_config = LenderConfig()
    
    # Get ANZ config only
    anz_config = lender_config.get_lender_by_id("anz")
    
    print(f"\n{'='*80}")
    print(f"Testing ANZ with Enhanced Filter Detection")
    print(f"URLs: {anz_config['collection_urls']}")
    print(f"{'='*80}\n")
    
    # Create workflow with ANZ only
    workflow = CollectionWorkflow(
        settings_manager=settings_manager,
        lender_config=lender_config
    )
    
    # Override to collect ANZ only
    workflow.lender_config._lenders = [anz_config]
    
    # Run collection
    await workflow.run()
    
    print(f"\n{'='*80}")
    print(f"✅ Collection complete! Check data/current/by_lender/ANZ.json")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(test_anz())

