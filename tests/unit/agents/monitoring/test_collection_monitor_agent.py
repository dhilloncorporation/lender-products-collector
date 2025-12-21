"""Test cases for CollectionMonitorAgent."""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.agents.monitoring.collection_monitor import CollectionMonitorAgent


class TestCollectionMonitorAgent:
    """Test cases for CollectionMonitorAgent."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir

    @pytest.fixture
    def monitor(self, temp_dir):
        """Create CollectionMonitorAgent instance."""
        log_path = Path(temp_dir) / "monitor.log"
        return CollectionMonitorAgent(log_path=str(log_path))

    def test_init(self, monitor, temp_dir):
        """Test monitor initialization."""
        assert monitor.log_path == Path(temp_dir) / "monitor.log"
        assert monitor.log_path.parent.exists()
        assert monitor.metrics == {}
        assert monitor.alerts == []

    def test_init_custom_log_path(self):
        """Test initialization with custom log path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "custom" / "monitor.log"
            monitor = CollectionMonitorAgent(log_path=str(log_path))
            
            assert monitor.log_path == log_path
            assert log_path.parent.exists()

    def test_log_collection_start(self, monitor):
        """Test logging collection start."""
        monitor.log_collection_start("ANZ", "scheduled")
        
        assert "ANZ_scheduled_start" in monitor.metrics
        assert isinstance(monitor.metrics["ANZ_scheduled_start"], str)
        
        # Verify timestamp format
        timestamp = monitor.metrics["ANZ_scheduled_start"]
        datetime.fromisoformat(timestamp)  # Should not raise exception

    def test_log_collection_start_manual(self, monitor):
        """Test logging manual collection start."""
        monitor.log_collection_start("CBA", "manual")
        
        assert "CBA_manual_start" in monitor.metrics

    def test_log_collection_complete_success(self, monitor):
        """Test logging successful collection completion."""
        monitor.log_collection_complete(
            lender="ANZ",
            collection_type="scheduled",
            products_collected=5,
            duration_seconds=30.5,
            success=True
        )
        
        key = "ANZ_scheduled_complete"
        assert key in monitor.metrics
        
        collection_data = monitor.metrics[key]
        assert collection_data["lender"] == "ANZ"
        assert collection_data["collection_type"] == "scheduled"
        assert collection_data["products_collected"] == 5
        assert collection_data["duration_seconds"] == 30.5
        assert collection_data["success"] is True
        assert collection_data["error_message"] is None
        assert "timestamp" in collection_data

    def test_log_collection_complete_failure(self, monitor):
        """Test logging failed collection completion."""
        monitor.log_collection_complete(
            lender="CBA",
            collection_type="scheduled",
            products_collected=0,
            duration_seconds=15.0,
            success=False,
            error_message="Network timeout"
        )
        
        key = "CBA_scheduled_complete"
        assert key in monitor.metrics
        
        collection_data = monitor.metrics[key]
        assert collection_data["success"] is False
        assert collection_data["error_message"] == "Network timeout"
        
        # Should create an alert
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]["type"] == "collection_failure"
        assert "CBA" in monitor.alerts[0]["message"]

    def test_check_data_freshness_no_stale_data(self, monitor):
        """Test data freshness check with no stale data."""
        # Add recent collection
        recent_time = datetime.now() - timedelta(hours=1)
        monitor.metrics["ANZ_scheduled_complete"] = {
            "lender": "ANZ",
            "success": True,
            "timestamp": recent_time.isoformat()
        }
        
        result = monitor.check_data_freshness(max_age_hours=24)
        
        assert result["max_age_hours"] == 24
        assert result["stale_lenders"] == []
        assert result["total_stale"] == 0

    def test_check_data_freshness_with_stale_data(self, monitor):
        """Test data freshness check with stale data."""
        # Add stale collection
        stale_time = datetime.now() - timedelta(hours=25)
        monitor.metrics["ANZ_scheduled_complete"] = {
            "lender": "ANZ",
            "success": True,
            "timestamp": stale_time.isoformat()
        }
        
        result = monitor.check_data_freshness(max_age_hours=24)
        
        assert result["total_stale"] == 1
        assert len(result["stale_lenders"]) == 1
        assert result["stale_lenders"][0]["lender"] == "ANZ"
        assert result["stale_lenders"][0]["hours_old"] > 24
        
        # Should create an alert
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]["type"] == "stale_data"

    def test_get_collection_stats_success(self, monitor):
        """Test getting collection statistics."""
        # Add successful collections
        recent_time = datetime.now() - timedelta(hours=1)
        monitor.metrics["ANZ_scheduled_complete"] = {
            "lender": "ANZ",
            "success": True,
            "products_collected": 5,
            "timestamp": recent_time.isoformat()
        }
        
        monitor.metrics["CBA_scheduled_complete"] = {
            "lender": "CBA",
            "success": True,
            "products_collected": 3,
            "timestamp": recent_time.isoformat()
        }
        
        stats = monitor.get_collection_stats(hours=24)
        
        assert stats["period_hours"] == 24
        assert stats["successful_collections"] == 2
        assert stats["failed_collections"] == 0
        assert stats["total_products_collected"] == 8
        assert stats["success_rate"] == 1.0
        
        # Check lender breakdown
        assert "ANZ" in stats["lender_breakdown"]
        assert "CBA" in stats["lender_breakdown"]
        assert stats["lender_breakdown"]["ANZ"]["successful"] == 1
        assert stats["lender_breakdown"]["ANZ"]["total_products"] == 5

    def test_get_system_health_healthy(self, monitor):
        """Test system health check with healthy status."""
        # Add recent successful collections
        recent_time = datetime.now() - timedelta(hours=1)
        monitor.metrics["ANZ_scheduled_complete"] = {
            "lender": "ANZ",
            "success": True,
            "products_collected": 5,
            "timestamp": recent_time.isoformat()
        }
        
        health = monitor.get_system_health()
        
        assert health["status"] == "healthy"
        assert "timestamp" in health
        assert "data_freshness" in health
        assert "collection_stats" in health
        assert "active_alerts" in health
        assert "recent_alerts" in health

    def test_create_alert(self, monitor):
        """Test creating alerts."""
        monitor._create_alert("test_alert", "Test message", "warning")
        
        assert len(monitor.alerts) == 1
        alert = monitor.alerts[0]
        assert alert["type"] == "test_alert"
        assert alert["message"] == "Test message"
        assert alert["severity"] == "warning"
        assert "timestamp" in alert

    def test_export_metrics_default_path(self, monitor):
        """Test exporting metrics with default path."""
        # Add some data
        monitor.metrics["test_metric"] = "test_value"
        monitor.alerts = [{"type": "test", "message": "test"}]
        
        with patch('builtins.open', mock_open()) as mock_file:
            file_path = monitor.export_metrics()
            
            assert file_path.startswith("metrics_export_")
            assert file_path.endswith(".json")
            mock_file.assert_called_once()

    def test_integration_full_workflow(self, monitor):
        """Test full monitoring workflow integration."""
        # Start collection
        monitor.log_collection_start("ANZ", "scheduled")
        
        # Complete collection successfully
        monitor.log_collection_complete(
            lender="ANZ",
            collection_type="scheduled",
            products_collected=5,
            duration_seconds=30.0,
            success=True
        )
        
        # Check data freshness
        freshness = monitor.check_data_freshness()
        assert freshness["total_stale"] == 0
        
        # Get collection stats
        stats = monitor.get_collection_stats()
        assert stats["successful_collections"] == 1
        assert stats["total_products_collected"] == 5
        
        # Get system health
        health = monitor.get_system_health()
        assert health["status"] == "healthy"
        
        # Export metrics
        with patch('builtins.open', mock_open()), \
             patch('json.dump'):
            file_path = monitor.export_metrics()
            assert file_path.startswith("metrics_export_")

