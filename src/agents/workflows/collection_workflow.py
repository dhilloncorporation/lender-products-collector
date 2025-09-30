"""LangGraph workflow for loan product collection."""

import logging
from datetime import datetime
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END

# Checkpointer is optional - only needed for persistence
try:
    from langgraph_checkpoint.sqlite import SqliteSaver
    HAS_CHECKPOINTER = True
except ImportError:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        HAS_CHECKPOINTER = True
    except ImportError:
        SqliteSaver = None
        HAS_CHECKPOINTER = False
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ...configs.settings_manager import SettingsManager
from ...configs.lender_config import LenderConfigManager
from ..collector.playwright_collector import PlaywrightCollectorAgent
from ..discovery.google_search_discovery import GoogleSearchDiscovery
from ...services.json_storage import JSONStorageService

logger = logging.getLogger(__name__)


class CollectionState(TypedDict):
    """State for the collection workflow."""
    lenders: List[Dict[str, Any]]
    current_lender: str
    current_lender_urls: List[str]  # Discovered URLs for current lender
    collection_results: Dict[str, Any]
    errors: List[str]
    completed_lenders: List[str]
    total_lenders: int
    success_count: int
    failure_count: int


class CollectionWorkflow:
    """LangGraph workflow for orchestrating loan product collection."""
    
    def __init__(self, settings_manager: SettingsManager, lender_config_manager: LenderConfigManager):
        self.settings_manager = settings_manager
        self.lender_config_manager = lender_config_manager
        self.langchain_settings = settings_manager.get_langchain_settings()
        self.langgraph_settings = settings_manager.get_langgraph_settings()
        
        # Initialize LLM (for any AI-powered tasks, not for data extraction)
        self.llm = ChatOpenAI(
            model=self.langchain_settings.model_name,
            temperature=self.langchain_settings.temperature,
            max_tokens=self.langchain_settings.max_tokens,
            api_key=self.langchain_settings.api_key_env
        )
        
        # Initialize storage service
        self.storage = JSONStorageService()
        
        # Initialize discovery service
        self.discovery = GoogleSearchDiscovery()
        
        # Build the workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow for collecting loan products.
        
        This creates a state machine that processes lenders sequentially:
        1. Initialize: Load lender list
        2. Loop for each lender:
           - Select next lender
           - Collect products (Playwright scraping)
           - Process results (validate & save)
           - Check if done
        3. Finalize: Summary report
        """
        # Create a state graph with CollectionState schema
        # This manages the workflow state across all steps
        workflow = StateGraph(CollectionState)
        
        # ==============================================================================
        # NODES: Each node is a step in the workflow that processes the state
        # ==============================================================================
        
        # Node 1: Load configuration and initialize state
        workflow.add_node("initialize", self._initialize_collection)
        
        # Node 2: Select next lender to process (by priority)
        workflow.add_node("select_lender", self._select_lender)
        
        # Node 3: Discover URLs using Google search
        # This finds the right pages for each lender dynamically
        workflow.add_node("discover_urls", self._discover_urls)
        
        # Node 4: Scrape lender website using Playwright
        # This is the main data collection step
        workflow.add_node("collect_products", self._collect_products)
        
        # Node 4: Validate collected data and save to JSON storage
        workflow.add_node("process_results", self._process_results)
        
        # Node 5: Check progress (how many lenders completed)
        workflow.add_node("check_completion", self._check_completion)
        
        # Node 6: Final summary and cleanup
        workflow.add_node("finalize", self._finalize_collection)
        
        # ==============================================================================
        # EDGES: Define the flow between nodes
        # ==============================================================================
        
        # Start here
        workflow.set_entry_point("initialize")
        
        # Linear flow for the main collection loop
        workflow.add_edge("initialize", "select_lender")       # After init → select first lender
        workflow.add_edge("select_lender", "discover_urls")    # After select → find URLs via Google
        workflow.add_edge("discover_urls", "collect_products") # After discovery → scrape websites
        workflow.add_edge("collect_products", "process_results") # After scrape → validate & save
        workflow.add_edge("process_results", "check_completion") # After save → check if done
        
        # DECISION POINT: Continue or finish?
        # This creates a loop - it calls _should_continue() to decide
        workflow.add_conditional_edges(
            "check_completion",           # From this node...
            self._should_continue,        # Call this function to decide...
            {
                "continue": "select_lender",  # If more lenders → loop back to select next
                "finish": "finalize"          # If all done → go to finalize
            }
        )
        
        # Final step ends the workflow
        workflow.add_edge("finalize", END)
        
        # ==============================================================================
        # COMPILE: Convert the graph definition into an executable workflow
        # ==============================================================================
        
        # Checkpointer is optional - allows resuming interrupted workflows
        # Currently disabled due to module compatibility issues
        workflow = workflow.compile()
        logger.info("LangGraph workflow compiled without checkpointer")
        
        return workflow
        
        # WORKFLOW VISUALIZATION:
        # 
        #   START
        #     ↓
        #  initialize (load lenders from lenders.json)
        #     ↓
        #  ┌──────────────────────────────┐
        #  │  select_lender (by priority) │ ←─┐
        #  │         ↓                     │   │
        #  │  discover_urls (Google)      │   │  LOOP
        #  │         ↓                     │   │  (for each lender)
        #  │  collect_products (Playwright)│   │
        #  │         ↓                     │   │
        #  │  process_results (save)      │   │
        #  │         ↓                     │   │
        #  │  check_completion            │   │
        #  │         ↓                     │   │
        #  │    [decision]                │   │
        #  └─────────┬────────────────────┘   │
        #            ├─ continue ──────────────┘ (more lenders)
        #            │
        #            └─ finish ───→ finalize → END
        #
    
    def _initialize_collection(self, state: CollectionState) -> CollectionState:
        """Initialize the collection process."""
        logger.info("Initializing collection workflow")
        
        # Get enabled lenders and convert to dict for state
        lenders_objects = self.lender_config_manager.get_enabled_lenders()
        lenders = [
            {
                "abbreviation": lender.name,
                "lender_name": lender.display_name,
                "priority": 1  # Default priority
            }
            for lender in lenders_objects
        ]
        
        return {
            **state,
            "lenders": lenders,
            "total_lenders": len(lenders),
            "completed_lenders": [],
            "success_count": 0,
            "failure_count": 0,
            "collection_results": {},
            "errors": []
        }
    
    def _select_lender(self, state: CollectionState) -> CollectionState:
        """Select the next lender to process."""
        completed = set(state["completed_lenders"])
        available_lenders = [
            lender for lender in state["lenders"] 
            if lender["abbreviation"] not in completed
        ]
        
        if not available_lenders:
            return state
        
        # Select lender with highest priority (lowest priority number)
        selected_lender = min(available_lenders, key=lambda x: x.get("priority", 999))
        
        logger.info(f"Selected lender: {selected_lender['abbreviation']}")
        
        return {
            **state,
            "current_lender": selected_lender["abbreviation"],
            "current_lender_urls": []  # Will be populated by discover_urls
        }
    
    async def _discover_urls(self, state: CollectionState) -> CollectionState:
        """
        Get URLs for the current lender.
        
        Strategy:
        1. Use collection_urls from lender config (if provided) ✅ PREFERRED
        2. Try Google search discovery (with 5s delays to avoid CAPTCHA) ✅ FALLBACK
        3. Error if both fail (no guessing URLs)
        """
        lender_abbr = state["current_lender"]
        logger.info(f"Getting URLs for {lender_abbr}...")
        
        try:
            # Get lender configuration
            lender_config = self.lender_config_manager.get_lender_by_abbreviation(lender_abbr)
            if not lender_config:
                raise ValueError(f"No configuration found for lender: {lender_abbr}")
            
            # STRATEGY 1: Use configured URLs (preferred)
            if "collection_urls" in lender_config and lender_config["collection_urls"]:
                urls = lender_config["collection_urls"]
                logger.info(f"✅ Using {len(urls)} configured URLs for {lender_abbr}")
                for url in urls:
                    logger.info(f"   - {url}")
                
                return {
                    **state,
                    "current_lender_urls": urls
                }
            
            # STRATEGY 2: Try Google search discovery (with delays)
            logger.info(f"⚠️  No configured URLs found in lenders.json")
            logger.info(f"🔍 Attempting Google search for {lender_abbr}...")
            logger.info(f"⏱️  Using 5s delays between searches to avoid CAPTCHA")
            
            lender_name = lender_config["lender_name"]
            lender_domain = lender_config.get("domain", f"{lender_abbr.lower()}.com.au")
            
            discovered_pages = await self.discovery.discover_lender_pages(
                lender_name=lender_name,
                lender_domain=lender_domain
            )
            
            # Flatten discovered URLs
            urls = []
            urls.extend(discovered_pages.get("interest_rates", []))
            urls.extend(discovered_pages.get("products", []))
            urls.extend(discovered_pages.get("comparison", []))
            
            # Remove duplicates
            seen = set()
            unique_urls = []
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            final_urls = unique_urls[:3]
            
            if final_urls:
                logger.info(f"✅ Google discovered {len(final_urls)} URLs for {lender_abbr}")
                for url in final_urls:
                    logger.info(f"   - {url}")
                
                return {
                    **state,
                    "current_lender_urls": final_urls
                }
            
            # NO FALLBACK - Error if both strategies fail
            error_msg = (
                f"❌ Failed to get URLs for {lender_abbr}: "
                f"No collection_urls in config AND Google search failed (likely CAPTCHA). "
                f"Please add collection_urls to src/configs/lenders.json for this lender."
            )
            logger.error(error_msg)
            
            return {
                **state,
                "current_lender_urls": [],
                "errors": state["errors"] + [error_msg]
            }
        
        except Exception as e:
            logger.error(f"URL discovery failed for {lender_abbr}: {e}")
            return {
                **state,
                "current_lender_urls": [],
                "errors": state["errors"] + [f"URL discovery exception for {lender_abbr}: {str(e)}"]
            }
    
    async def _collect_products(self, state: CollectionState) -> CollectionState:
        """
        Collect products from the current lender using Playwright.
        
        Uses the URLs discovered by Google search in the previous step.
        """
        lender_abbr = state["current_lender"]
        urls = state["current_lender_urls"]
        
        logger.info(f"Collecting products from {lender_abbr} ({len(urls)} URLs)")
        
        try:
            # Get lender configuration
            lender_config = self.lender_config_manager.get_lender_by_abbreviation(lender_abbr)
            if not lender_config:
                raise ValueError(f"No configuration found for lender: {lender_abbr}")
            
            # Initialize collector agent
            async with PlaywrightCollectorAgent(headless=True) as collector:
                all_products = []
                
                # Scrape each discovered URL
                for url in urls:
                    products = await collector.collect_from_url(
                        url=url,
                        lender_name=lender_config["lender_name"]
                    )
                    all_products.extend(products)
                
                # Save collected products to storage
                if all_products:
                    await self.storage.save_current_products(
                        products=all_products,
                        lender=lender_abbr
                    )
                    
                    # Save snapshot
                    snapshot_paths = await self.storage.save_snapshot(
                        products=all_products,
                        lender=lender_abbr
                    )
                    
                    # Update index
                    await self.storage.update_index(
                        lender=lender_abbr,
                        status="success",
                        products_count=len(all_products),
                        snapshot_path=snapshot_paths.get('parsed', '')
                    )
                
                result = {
                    "lender": lender_abbr,
                    "products": [p.model_dump() for p in all_products],
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "count": len(all_products)
                }
                
                logger.info(f"Collected {len(all_products)} products from {lender_abbr}")
            
            return {
                **state,
                "collection_results": {
                    **state["collection_results"],
                    lender_abbr: result
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting from {lender_abbr}: {str(e)}")
            
            # Update index with failure
            await self.storage.update_index(
                lender=lender_abbr,
                status="failure",
                products_count=0,
                snapshot_path=""
            )
            
            return {
                **state,
                "errors": state["errors"] + [f"{lender_abbr}: {str(e)}"],
                "collection_results": {
                    **state["collection_results"],
                    lender_abbr: {
                        "lender": lender_abbr,
                        "products": [],
                        "status": "failure",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                }
            }
    
    def _process_results(self, state: CollectionState) -> CollectionState:
        """Process and validate collection results."""
        lender_abbr = state["current_lender"]
        result = state["collection_results"].get(lender_abbr, {})
        
        if result.get("status") == "success":
            logger.info(f"Successfully collected from {lender_abbr}")
            return {
                **state,
                "completed_lenders": state["completed_lenders"] + [lender_abbr],
                "success_count": state["success_count"] + 1
            }
        else:
            logger.warning(f"Failed to collect from {lender_abbr}")
            return {
                **state,
                "completed_lenders": state["completed_lenders"] + [lender_abbr],
                "failure_count": state["failure_count"] + 1
            }
    
    def _check_completion(self, state: CollectionState) -> CollectionState:
        """Check if collection is complete."""
        total = state["total_lenders"]
        completed = len(state["completed_lenders"])
        
        logger.info(f"Progress: {completed}/{total} lenders completed")
        
        return state
    
    def _should_continue(self, state: CollectionState) -> str:
        """Determine if collection should continue."""
        total = state["total_lenders"]
        completed = len(state["completed_lenders"])
        
        if completed < total:
            return "continue"
        else:
            return "finish"
    
    def _finalize_collection(self, state: CollectionState) -> CollectionState:
        """Finalize the collection process."""
        logger.info("Finalizing collection workflow")
        logger.info(f"Collection complete: {state['success_count']} success, {state['failure_count']} failures")
        
        return state
    
    async def run_collection(self, config: Dict[str, Any] = None) -> CollectionState:
        """Run the collection workflow."""
        logger.info("Starting collection workflow")
        
        initial_state = CollectionState(
            lenders=[],
            current_lender="",
            current_lender_urls=[],
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=0,
            success_count=0,
            failure_count=0
        )
        
        # Run the workflow
        final_state = await self.workflow.ainvoke(initial_state, config=config)
        
        logger.info("Collection workflow completed")
        return final_state
