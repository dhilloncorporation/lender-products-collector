"""
Collection Workflow Orchestrator Agent

ROLE: Main Orchestrator
PURPOSE: Coordinates the entire loan product collection process using LangGraph state machine

This is the primary orchestrator agent that manages the end-to-end collection workflow:
1. Initializes collection state and loads lender configurations
2. Selects lenders to process (by priority)
3. Discovers URLs for each lender (via Discovery Agent)
4. Analyzes page structure to determine best extraction strategy
5. Collects products (via Collector Agent)
6. Processes and saves results (via Storage Agent)
7. Tracks progress and handles errors
8. Finalizes with summary report

WORKFLOW NODES (Sequential Execution):
- initialize: Load lender configurations
- select_lender: Pick next lender to process
- discover_urls: Find URLs for current lender via Discovery Agent
- collect_products: Analyze page structure and scrape data via Collector Agent
- process_results: Validate and save via Storage Agent
- check_completion: Track progress
- finalize: Generate summary

EXECUTION MODEL:
- Nodes execute SEQUENTIALLY (one completes before next starts)
- Each node receives state, processes it, returns updated state
- Workflow waits for each node to complete before proceeding
- State flows through the workflow: State → Node → Updated State → Next Node

DEPENDENCIES:
- Discovery Agent (WebSearchDiscovery)
- Collector Agent (PlaywrightCollectorAgent)
- Storage Agent (ProductStorageAgent)
- Configuration Managers (YamlSettingsManager, LenderConfigManager)

USAGE:
    workflow = CollectionWorkflow(settings_manager, lender_config_manager)
    final_state = await workflow.run_collection()
"""

import asyncio
import logging
import os
import re
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

from ...configs.settings_manager import YamlSettingsManager
from ...configs.lender_config import LenderConfigManager
from ..collector.playwright_collector import PlaywrightCollectorAgent
from ..discovery.web_search_discovery import WebSearchDiscovery
from ..storage.product_storage import ProductStorageAgent

logger = logging.getLogger(__name__)


class CollectionState(TypedDict):
    """State for the collection workflow."""
    lenders: List[Dict[str, Any]]
    current_lender: str
    current_lender_urls: List[str]  # Discovered URLs for current lender
    current_lender_products: List[Dict[str, Any]]  # Collected products (before storage)
    collection_results: Dict[str, Any]  # Final results after storage
    errors: List[str]
    completed_lenders: List[str]
    total_lenders: int
    success_count: int
    failure_count: int


class CollectionWorkflow:
    """
    LangGraph workflow orchestrator for loan product collection.
    
    This agent coordinates all other agents in a state machine workflow to collect
    loan product data from multiple lenders. It uses LangGraph to manage state and
    control flow between different collection steps.
    
    Attributes:
        settings_manager: Configuration manager for system settings
        lender_config_manager: Configuration manager for lender data
        storage_agent: Product storage agent for saving collected products
        discovery: Web search discovery agent for finding URLs
        workflow: Compiled LangGraph state machine
    
    Workflow Flow (Cyclic Graph with Bounded Loop):
        1. Initialize → Load lenders from config
        2. [LOOP START] Select Lender → Pick next lender by priority
        3. Discover URLs → Find pages for current lender via Discovery Agent
        4. Collect Products → Analyze page structure and scrape via Collector Agent
        5. Process Results → Save via Storage Agent
        6. Check Completion → Decision point:
           - If more lenders: Loop back to step 2
           - If all done: Proceed to step 7
        7. Finalize → Generate summary → END
        
    Note: This is a CYCLIC graph (not acyclic DAG) with a bounded while-loop pattern.
    
    Example:
        >>> workflow = CollectionWorkflow(settings_manager, lender_config_manager)
        >>> final_state = await workflow.run_collection()
        >>> print(f"Success: {final_state['success_count']}, Failed: {final_state['failure_count']}")
    """
    
    def __init__(self, settings_manager: YamlSettingsManager, lender_config_manager: LenderConfigManager):
        self.settings_manager = settings_manager
        self.lender_config_manager = lender_config_manager
        self.environment = settings_manager.get_environment()
        self.debug = settings_manager.get_debug()
        self.validation = settings_manager.get_validation()
        self.ai = settings_manager.get_ai()
        
        # Initialize LLM (for any AI-powered tasks, not for data extraction)
        # Make LLM optional for testing without API key
        try:
            api_key = os.getenv(self.ai.openai_api_key_env)
            if api_key:
                self.llm = ChatOpenAI(
                    model=self.ai.openai_model,
                    temperature=self.ai.temperature,
                    max_tokens=self.ai.max_tokens,
                    api_key=api_key
                )
            else:
                logger.warning("OpenAI API key not found - LLM features disabled")
                self.llm = None
        except Exception as e:
            logger.warning(f"Failed to initialize LLM: {e} - LLM features disabled")
            self.llm = None
        
        # Initialize storage agent
        self.storage_agent = ProductStorageAgent()
        
        # Initialize discovery agent with settings
        self.discovery = WebSearchDiscovery(settings_manager)
        
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
        
        GRAPH STRUCTURE:
        - Type: CYCLIC GRAPH (not acyclic DAG)
        - Contains a conditional loop: check_completion → [continue → select_lender] or [finish → finalize]
        - Loop is BOUNDED: terminates when all lenders are processed
        - Pattern: While-loop (while lenders remain, process next lender)
        
        EXECUTION SEMANTICS:
        - Nodes execute SEQUENTIALLY (one completes before next starts)
        - Each node receives state as input
        - Each node returns updated state
        - Workflow waits for node completion before proceeding
        - State flows: initialize → select_lender → discover_urls → 
          collect_products → process_results → check_completion → [loop back to select_lender OR finalize]
        - Note: Page analysis is handled internally by the Collector Agent
        
        EXECUTION PATTERN (Example: 4 lenders):
        - workflow.ainvoke() called ONCE
        - initialize() executes ONCE (at start)
        - For EACH lender, the following workflow nodes execute in sequence:
          * select_lender() → discover_urls() → collect_products() → 
            process_results() → check_completion()
        - This sequence (select → discover → collect → process → check) 
          runs COMPLETELY for each lender before moving to the next
        - After each lender, check_completion() decides: continue or finish
        - If continue: loop back to select_lender() for next lender
        - If finish: proceed to finalize() → END
        - finalize() executes ONCE (at end)
        
        PER-LENDER NODE SEQUENCE:
        Each lender goes through this complete sequence:
        1. select_lender() - Selects the lender to process
        2. discover_urls() - Finds URLs for that lender
        3. collect_products() - Collects data from those URLs
        4. process_results() - Saves the collected data
        5. check_completion() - Checks if more lenders remain
           → If yes: Loop back to step 1 for next lender
           → If no: Proceed to finalize()
        
        CYCLE DETAILS:
        - Entry: check_completion node
        - Condition: _should_continue() checks if completed_lenders < total_lenders
        - If continue: loops back to select_lender (processes next lender)
        - If finish: proceeds to finalize → END (workflow terminates)
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
        
        # Node 3: Discover URLs for current lender
        # This finds the right pages for each lender dynamically
        workflow.add_node("discover_urls", self._discover_urls)
        
        # Node 4: Analyze page structure and collect products using Playwright
        # The collector agent handles both analysis and extraction internally
        workflow.add_node("collect_products", self._collect_products)
        
        # Node 5: Validate collected data and save to JSON storage
        workflow.add_node("process_results", self._process_results)
        
        # Node 6: Check progress (how many lenders completed)
        workflow.add_node("check_completion", self._check_completion)
        
        # Node 7: Final summary and cleanup
        workflow.add_node("finalize", self._finalize_collection)
        
        # ==============================================================================
        # EDGES: Define the flow between nodes
        # ==============================================================================
        
        # Start here
        workflow.set_entry_point("initialize")
        
        # Linear flow for the main collection loop
        workflow.add_edge("initialize", "select_lender")       # After init → select first lender
        workflow.add_edge("select_lender", "discover_urls")    # After select → find URLs for current lender
        workflow.add_edge("discover_urls", "collect_products") # After discovery → analyze & collect (fused)
        workflow.add_edge("collect_products", "process_results") # After collection → validate & save
        workflow.add_edge("process_results", "check_completion") # After save → check if done
        
        # DECISION POINT: Continue or finish?
        # This creates a loop - it calls _should_continue() to decide
        # NOTE: The MAIN LOOP (processing multiple lenders) is in the WORKFLOW, not in agents
        # - Agents are called sequentially for each lender (no loops in agents)
        # - The workflow loop is controlled by conditional edges
        # - Each agent processes ONE task per invocation (one lender, one URL at a time)
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
        
        return {
            **state,
            "current_lender": selected_lender["abbreviation"],
            "current_lender_urls": []  # Will be populated by discover_urls
        }
    
    async def _discover_urls(self, state: CollectionState) -> CollectionState:
        """
        Get URLs for the current lender.
        
        Delegates to WebSearchDiscovery agent.
        """
        lender_abbr = state["current_lender"]
        
        try:
            # Get lender configuration
            lender_config = self.lender_config_manager.get_lender_by_abbreviation(lender_abbr)
            if not lender_config:
                raise ValueError(f"No configuration found for lender: {lender_abbr}")
            
            # STRATEGY 1: Use configured URLs (preferred)
            if "collection_urls" in lender_config and lender_config["collection_urls"]:
                urls = lender_config["collection_urls"]
                return {
                    **state,
                    "current_lender_urls": urls
                }
            
            # STRATEGY 2: Delegate to discovery agent
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
                return {
                    **state,
                    "current_lender_urls": final_urls
                }
            
            # NO FALLBACK - Error if both strategies fail
            error_msg = (
                f"Failed to get URLs for {lender_abbr}: "
                f"No collection_urls in config AND Google search failed. "
                f"Please add collection_urls to src/configs/lenders.json for this lender."
            )
            
            return {
                **state,
                "current_lender_urls": [],
                "errors": state["errors"] + [error_msg]
            }
        
        except Exception as e:
            return {
                **state,
                "current_lender_urls": [],
                "errors": state["errors"] + [f"URL discovery exception for {lender_abbr}: {str(e)}"]
            }
    
    async def _collect_products(self, state: CollectionState) -> CollectionState:
        """
        Analyze page structure and collect products from the current lender.
        
        Delegates to PlaywrightCollectorAgent which handles both:
        - Page structure analysis (detects extraction strategies)
        - Product collection (using detected strategies)
        
        The collector agent is autonomous and makes its own decisions about
        which extraction strategy to use based on page structure.
        
        Storage is handled by _process_results node.
        """
        lender_abbr = state["current_lender"]
        urls = state["current_lender_urls"]
        
        try:
            # Get lender configuration
            lender_config = self.lender_config_manager.get_lender_by_abbreviation(lender_abbr)
            if not lender_config:
                raise ValueError(f"No configuration found for lender: {lender_abbr}")
            
            # Delegate collection to collector agent
            async with PlaywrightCollectorAgent(headless=True) as collector:
                all_products = []
                
                # Scrape each discovered URL with timing controls (orchestration logic)
                for i, url in enumerate(urls):
                    # Add delay between URLs of the same lender
                    if i > 0:
                        rate_limits = self.settings_manager.get_rate_limits()
                        delay = rate_limits.per_url_delay_seconds
                        await asyncio.sleep(delay)
                    
                    products = await collector.collect_from_url(
                        url=url,
                        lender_name=lender_config["lender_name"]
                    )
                    all_products.extend(products)
            
            # Store products in state for processing node (orchestration)
            return {
                **state,
                "current_lender_products": [p.model_dump() for p in all_products]
            }
                
        except Exception as e:
            # Store error in state for processing node
            return {
                **state,
                "current_lender_products": [],
                "errors": state["errors"] + [f"Collection error for {lender_abbr}: {str(e)}"]
            }
    
    async def _process_results(self, state: CollectionState) -> CollectionState:
        """
        Process and store collection results.
        
        Delegates to ProductStorageAgent for all storage operations.
        Updates workflow state with results.
        """
        lender_abbr = state["current_lender"]
        products_data = state.get("current_lender_products", [])
        
        # Convert dicts back to LoanProduct objects for storage agent
        from ...models import LoanProduct
        products = [LoanProduct(**p) for p in products_data] if products_data else []
        
        try:
            if products:
                # Delegate storage to storage agent
                await self.storage_agent.save_current_products(
                    products=products,
                    lender=lender_abbr
                )
                
                snapshot_paths = await self.storage_agent.save_snapshot(
                    products=products,
                    lender=lender_abbr
                )
                
                await self.storage_agent.update_index(
                    lender=lender_abbr,
                    status="success",
                    products_count=len(products),
                    snapshot_path=snapshot_paths.get('parsed', '')
                )
                
                result = {
                    "lender": lender_abbr,
                    "products": products_data,
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "count": len(products)
                }
                
                return {
                    **state,
                    "collection_results": {
                        **state["collection_results"],
                        lender_abbr: result
                    },
                    "completed_lenders": state["completed_lenders"] + [lender_abbr],
                    "success_count": state["success_count"] + 1
                }
            else:
                # No products collected
                await self.storage_agent.update_index(
                    lender=lender_abbr,
                    status="no_products",
                    products_count=0,
                    snapshot_path=""
                )
                
                result = {
                    "lender": lender_abbr,
                    "products": [],
                    "status": "no_products",
                    "timestamp": datetime.now().isoformat(),
                    "count": 0
                }
                
                return {
                    **state,
                    "collection_results": {
                        **state["collection_results"],
                        lender_abbr: result
                    },
                    "completed_lenders": state["completed_lenders"] + [lender_abbr],
                    "failure_count": state["failure_count"] + 1
                }
        
        except Exception as e:
            # Storage failed
            await self.storage_agent.update_index(
                lender=lender_abbr,
                status="failure",
                products_count=0,
                snapshot_path=""
            )
            
            result = {
                "lender": lender_abbr,
                "products": [],
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "count": 0,
                "error": str(e)
            }
            
            return {
                **state,
                "collection_results": {
                    **state["collection_results"],
                    lender_abbr: result
                },
                "completed_lenders": state["completed_lenders"] + [lender_abbr],
                "failure_count": state["failure_count"] + 1,
                "errors": state["errors"] + [f"Storage error for {lender_abbr}: {str(e)}"]
            }
    
    def _check_completion(self, state: CollectionState) -> CollectionState:
        """Check if collection is complete."""
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
        return state
    
    async def run_collection(self, config: Dict[str, Any] = None) -> CollectionState:
        """
        Run the collection workflow.
        
        This is the main entry point that initiates and finalizes the workflow.
        All detailed logging is handled by the individual agents.
        """
        logger.info("=" * 80)
        logger.info("Starting Loan Product Collection Workflow")
        logger.info("=" * 80)
        
        initial_state = CollectionState(
            lenders=[],
            current_lender="",
            current_lender_urls=[],
            current_lender_products=[],
            collection_results={},
            errors=[],
            completed_lenders=[],
            total_lenders=0,
            success_count=0,
            failure_count=0
        )
        
        # Run the workflow (SINGLE INVOCATION - loop happens internally)
        # The workflow.ainvoke() is called ONCE, but LangGraph internally handles
        # the loop via conditional edges until all lenders are processed
        final_state = await self.workflow.ainvoke(initial_state, config=config)
        
        # Final summary log
        logger.info("=" * 80)
        logger.info("Collection Workflow Completed")
        logger.info(f"Total Lenders: {final_state.get('total_lenders', 0)}")
        logger.info(f"Successful: {final_state.get('success_count', 0)}")
        logger.info(f"Failed: {final_state.get('failure_count', 0)}")
        logger.info("=" * 80)
        
        return final_state
