"""Test cases for CollectionSchedulerAgent."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.agents.scheduler.collection_scheduler import CollectionSchedulerAgent


class TestCollectionSchedulerAgent:
    """Test cases for CollectionSchedulerAgent."""

    @pytest.fixture
    def mock_config_manager(self):
        """Mock lender config manager."""
        config_manager = Mock()
        config_manager.get_enabled_lenders.return_value = [
            Mock(name="ANZ", abbreviation="ANZ"),
            Mock(name="CBA", abbreviation="CBA")
        ]
        config_manager.get_volatile_lenders.return_value = [
            Mock(name="ANZ", abbreviation="ANZ")
        ]
        return config_manager

    @pytest.fixture
    def mock_collector_agent(self):
        """Mock collector agent."""
        collector = Mock()
        collector.get_collected_products.return_value = []
        collector.collect_from_url = AsyncMock(return_value=[])
        return collector

    @pytest.fixture
    def scheduler_agent(self, mock_config_manager, mock_collector_agent):
        """Create CollectionSchedulerAgent instance with mocked dependencies."""
        with patch('src.agents.scheduler.collection_scheduler.FirecrawlCollectorAgent', return_value=mock_collector_agent), \
             patch('src.agents.scheduler.collection_scheduler.LenderConfigManager', return_value=mock_config_manager), \
             patch('src.agents.scheduler.collection_scheduler.AsyncIOScheduler') as mock_scheduler_class:
            
            mock_scheduler = Mock()
            mock_scheduler_class.return_value = mock_scheduler
            mock_scheduler.running = False
            mock_scheduler.get_jobs.return_value = []
            
            agent = CollectionSchedulerAgent()
            agent.scheduler = mock_scheduler
            agent.collector_agent = mock_collector_agent
            agent.config_manager = mock_config_manager
            
            return agent

    def test_init(self, scheduler_agent):
        """Test scheduler initialization."""
        assert scheduler_agent.scheduler is not None
        assert scheduler_agent.collector_agent is not None
        assert scheduler_agent.config_manager is not None
        assert scheduler_agent.collection_results == {}

    def test_start_scheduler(self, scheduler_agent):
        """Test starting the scheduler."""
        scheduler_agent.start_scheduler()
        
        # Verify jobs were added
        scheduler_agent.scheduler.add_job.assert_called()
        assert scheduler_agent.scheduler.add_job.call_count >= 2  # Daily and hourly jobs
        
        # Verify scheduler was started
        scheduler_agent.scheduler.start.assert_called_once()

    def test_stop_scheduler(self, scheduler_agent):
        """Test stopping the scheduler."""
        scheduler_agent.stop_scheduler()
        
        scheduler_agent.scheduler.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_daily_collection_success(self, scheduler_agent):
        """Test successful daily collection."""
        # Mock successful collection
        scheduler_agent.collect_from_lender = AsyncMock(return_value={
            "lender": "ANZ",
            "success": True,
            "products_collected": 5
        })
        
        await scheduler_agent.run_daily_collection()
        
        # Verify collection results were stored
        assert "daily" in scheduler_agent.collection_results
        daily_result = scheduler_agent.collection_results["daily"]
        assert daily_result["successful"] == 2  # ANZ and CBA
        assert daily_result["failed"] == 0
        assert "timestamp" in daily_result
        assert "duration" in daily_result

    @pytest.mark.asyncio
    async def test_run_daily_collection_with_failures(self, scheduler_agent):
        """Test daily collection with some failures."""
        # Mock mixed results
        def mock_collect_from_lender(lender_config):
            if lender_config.name == "ANZ":
                return {"lender": "ANZ", "success": True, "products_collected": 5}
            else:
                raise Exception("Collection failed")
        
        scheduler_agent.collect_from_lender = AsyncMock(side_effect=mock_collect_from_lender)
        
        await scheduler_agent.run_daily_collection()
        
        # Verify collection results
        daily_result = scheduler_agent.collection_results["daily"]
        assert daily_result["successful"] == 1
        assert daily_result["failed"] == 1

    @pytest.mark.asyncio
    async def test_run_daily_collection_exception(self, scheduler_agent):
        """Test daily collection with exception."""
        # Mock exception during collection
        scheduler_agent.config_manager.get_enabled_lenders.side_effect = Exception("Config error")
        
        await scheduler_agent.run_daily_collection()
        
        # Verify error was handled
        daily_result = scheduler_agent.collection_results["daily"]
        assert "error" in daily_result
        assert daily_result["successful"] == 0

    @pytest.mark.asyncio
    async def test_run_hourly_collection(self, scheduler_agent):
        """Test hourly collection for volatile lenders."""
        # Mock successful collection
        scheduler_agent.collect_from_lender = AsyncMock(return_value={
            "lender": "ANZ",
            "success": True,
            "products_collected": 3
        })
        
        await scheduler_agent.run_hourly_collection()
        
        # Verify collection was called for volatile lenders
        scheduler_agent.collect_from_lender.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_hourly_collection_with_failure(self, scheduler_agent):
        """Test hourly collection with failure."""
        # Mock failure
        scheduler_agent.collect_from_lender = AsyncMock(side_effect=Exception("Collection failed"))
        
        await scheduler_agent.run_hourly_collection()
        
        # Should handle error gracefully
        scheduler_agent.collect_from_lender.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_from_lender_success(self, scheduler_agent):
        """Test successful collection from lender."""
        # Mock lender adapter
        mock_adapter = Mock()
        mock_adapter.lender_name = "ANZ"
        mock_adapter.get_collection_urls.return_value = ["https://anz.com.au/rates"]
        mock_adapter.get_agent_prompt.return_value = "Extract loan products"
        mock_adapter.normalize_products.return_value = [{"name": "Test Product"}]
        
        # Mock collector agent
        scheduler_agent.collector_agent.collect_from_url = AsyncMock(return_value=[
            {"name": "Raw Product", "rate": "6.5%"}
        ])
        
        result = await scheduler_agent.collect_from_lender(mock_adapter)
        
        assert result["lender"] == "ANZ"
        assert result["success"] is True
        assert result["urls_processed"] == 1
        assert result["products_collected"] == 1
        assert result["products_normalized"] == 1

    @pytest.mark.asyncio
    async def test_collect_from_lender_failure(self, scheduler_agent):
        """Test collection failure from lender."""
        # Mock lender adapter that raises exception
        mock_adapter = Mock()
        mock_adapter.lender_name = "CBA"
        mock_adapter.get_collection_urls.side_effect = Exception("URL error")
        
        result = await scheduler_agent.collect_from_lender(mock_adapter)
        
        assert result["lender"] == "CBA"
        assert result["success"] is False
        assert "error" in result

    def test_get_collection_status(self, scheduler_agent):
        """Test getting collection status."""
        # Add some collection results
        scheduler_agent.collection_results = {
            "daily": {
                "timestamp": datetime.now().isoformat(),
                "successful": 2,
                "failed": 0
            }
        }
        
        # Mock scheduler status
        scheduler_agent.scheduler.running = True
        scheduler_agent.scheduler.get_jobs.return_value = [Mock(), Mock()]
        
        status = scheduler_agent.get_collection_status()
        
        assert status["scheduler_running"] is True
        assert status["active_jobs"] == 2
        assert "daily" in status["collection_results"]
        assert status["total_products_collected"] == 0

    def test_trigger_manual_collection_specific_lender(self, scheduler_agent):
        """Test triggering manual collection for specific lender."""
        # Mock lender adapters
        mock_adapter = Mock()
        mock_adapter.lender_name = "ANZ"
        scheduler_agent.lender_adapters = [mock_adapter]
        
        with patch('asyncio.create_task') as mock_create_task:
            scheduler_agent.trigger_manual_collection("ANZ")
            
            mock_create_task.assert_called_once()
            # Verify the task was created with collect_from_lender
            call_args = mock_create_task.call_args[0][0]
            assert call_args == scheduler_agent.collect_from_lender(mock_adapter)

    def test_trigger_manual_collection_all_lenders(self, scheduler_agent):
        """Test triggering manual collection for all lenders."""
        with patch('asyncio.create_task') as mock_create_task:
            scheduler_agent.trigger_manual_collection()
            
            mock_create_task.assert_called_once()
            # Verify the task was created with run_daily_collection
            call_args = mock_create_task.call_args[0][0]
            assert call_args == scheduler_agent.run_daily_collection()

    def test_trigger_manual_collection_lender_not_found(self, scheduler_agent):
        """Test triggering manual collection for non-existent lender."""
        scheduler_agent.lender_adapters = []
        
        with patch('asyncio.create_task') as mock_create_task:
            scheduler_agent.trigger_manual_collection("NONEXISTENT")
            
            # Should not create task for non-existent lender
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_from_lender_multiple_urls(self, scheduler_agent):
        """Test collection from lender with multiple URLs."""
        # Mock lender adapter with multiple URLs
        mock_adapter = Mock()
        mock_adapter.lender_name = "ANZ"
        mock_adapter.get_collection_urls.return_value = [
            "https://anz.com.au/rates",
            "https://anz.com.au/products"
        ]
        mock_adapter.get_agent_prompt.return_value = "Extract loan products"
        mock_adapter.normalize_products.return_value = [{"name": "Test Product"}]
        
        # Mock collector agent
        scheduler_agent.collector_agent.collect_from_url = AsyncMock(return_value=[
            {"name": "Raw Product", "rate": "6.5%"}
        ])
        
        result = await scheduler_agent.collect_from_lender(mock_adapter)
        
        assert result["urls_processed"] == 2
        assert result["products_collected"] == 2  # 1 product per URL
        assert scheduler_agent.collector_agent.collect_from_url.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_from_lender_empty_urls(self, scheduler_agent):
        """Test collection from lender with no URLs."""
        # Mock lender adapter with no URLs
        mock_adapter = Mock()
        mock_adapter.lender_name = "ANZ"
        mock_adapter.get_collection_urls.return_value = []
        mock_adapter.get_agent_prompt.return_value = "Extract loan products"
        mock_adapter.normalize_products.return_value = []
        
        result = await scheduler_agent.collect_from_lender(mock_adapter)
        
        assert result["urls_processed"] == 0
        assert result["products_collected"] == 0
        assert result["products_normalized"] == 0

    def test_scheduler_job_configuration(self, scheduler_agent):
        """Test scheduler job configuration."""
        scheduler_agent.start_scheduler()
        
        # Verify daily job was added
        daily_job_call = None
        hourly_job_call = None
        
        for call in scheduler_agent.scheduler.add_job.call_args_list:
            args, kwargs = call
            if "daily_collection" in kwargs.get("id", ""):
                daily_job_call = call
            elif "hourly_collection" in kwargs.get("id", ""):
                hourly_job_call = call
        
        assert daily_job_call is not None
        assert hourly_job_call is not None
        
        # Verify job names
        assert daily_job_call[1]["name"] == "Daily Loan Product Collection"
        assert hourly_job_call[1]["name"] == "Hourly Collection for Volatile Lenders"

    @pytest.mark.asyncio
    async def test_collection_results_storage(self, scheduler_agent):
        """Test collection results storage."""
        # Mock successful collection
        scheduler_agent.collect_from_lender = AsyncMock(return_value={
            "lender": "ANZ",
            "success": True,
            "products_collected": 5
        })
        
        await scheduler_agent.run_daily_collection()
        
        # Verify results structure
        daily_result = scheduler_agent.collection_results["daily"]
        assert "timestamp" in daily_result
        assert "duration" in daily_result
        assert "successful" in daily_result
        assert "failed" in daily_result
        assert "total_products" in daily_result
        
        # Verify timestamp format
        datetime.fromisoformat(daily_result["timestamp"])
        
        # Verify duration is positive
        assert daily_result["duration"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_collections(self, scheduler_agent):
        """Test concurrent collection handling."""
        # Mock slow collection
        async def slow_collect_from_lender(lender_config):
            await asyncio.sleep(0.1)  # Simulate slow collection
            return {
                "lender": lender_config.name,
                "success": True,
                "products_collected": 3
            }
        
        scheduler_agent.collect_from_lender = slow_collect_from_lender
        
        start_time = datetime.now()
        await scheduler_agent.run_daily_collection()
        duration = (datetime.now() - start_time).total_seconds()
        
        # Should complete in parallel, not sequentially
        # With 2 lenders and 0.1s each, should take ~0.1s, not 0.2s
        assert duration < 0.15  # Allow some margin for overhead

    def test_scheduler_lifecycle(self, scheduler_agent):
        """Test scheduler start/stop lifecycle."""
        # Start scheduler
        scheduler_agent.start_scheduler()
        assert scheduler_agent.scheduler.start.called
        
        # Stop scheduler
        scheduler_agent.stop_scheduler()
        assert scheduler_agent.scheduler.shutdown.called

    @pytest.mark.asyncio
    async def test_error_handling_in_collect_from_lender(self, scheduler_agent):
        """Test error handling in collect_from_lender method."""
        # Mock adapter that raises exception during normalization
        mock_adapter = Mock()
        mock_adapter.lender_name = "ANZ"
        mock_adapter.get_collection_urls.return_value = ["https://anz.com.au/rates"]
        mock_adapter.get_agent_prompt.return_value = "Extract loan products"
        mock_adapter.normalize_products.side_effect = Exception("Normalization failed")
        
        scheduler_agent.collector_agent.collect_from_url = AsyncMock(return_value=[
            {"name": "Raw Product", "rate": "6.5%"}
        ])
        
        result = await scheduler_agent.collect_from_lender(mock_adapter)
        
        assert result["success"] is False
        assert "error" in result
        assert "Normalization failed" in result["error"]

