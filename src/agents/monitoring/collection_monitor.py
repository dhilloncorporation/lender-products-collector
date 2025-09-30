"""Collection monitoring agent for tracking system health and performance."""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class CollectionMonitorAgent:
    """Agent that monitors collection performance, data freshness, and system health."""
    
    def __init__(self, log_path: str = "logs/collection_monitor.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, Any] = {}
        self.alerts: List[Dict[str, Any]] = []
    
    def log_collection_start(self, lender: str, collection_type: str = "scheduled"):
        """Log the start of a collection process."""
        timestamp = datetime.now()
        self.metrics[f"{lender}_{collection_type}_start"] = timestamp.isoformat()
        
        logger.info(f"Collection started for {lender} ({collection_type})")
    
    def log_collection_complete(
        self, 
        lender: str, 
        collection_type: str,
        products_collected: int,
        duration_seconds: float,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log the completion of a collection process."""
        timestamp = datetime.now()
        
        collection_data = {
            "lender": lender,
            "collection_type": collection_type,
            "products_collected": products_collected,
            "duration_seconds": duration_seconds,
            "success": success,
            "error_message": error_message,
            "timestamp": timestamp.isoformat()
        }
        
        # Store in metrics
        key = f"{lender}_{collection_type}_complete"
        self.metrics[key] = collection_data
        
        # Log the event
        if success:
            logger.info(f"Collection completed for {lender}: {products_collected} products in {duration_seconds:.2f}s")
        else:
            logger.error(f"Collection failed for {lender}: {error_message}")
            self._create_alert("collection_failure", f"Collection failed for {lender}: {error_message}")
    
    def check_data_freshness(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """Check data freshness and create alerts for stale data."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        stale_lenders = []
        
        for key, value in self.metrics.items():
            if key.endswith("_complete") and isinstance(value, dict):
                if value.get("success", False):
                    try:
                        collection_time = datetime.fromisoformat(value["timestamp"])
                        if collection_time < cutoff_time:
                            stale_lenders.append({
                                "lender": value["lender"],
                                "last_collection": collection_time.isoformat(),
                                "hours_old": (datetime.now() - collection_time).total_seconds() / 3600
                            })
                    except:
                        continue
        
        if stale_lenders:
            self._create_alert("stale_data", f"Stale data detected for {len(stale_lenders)} lenders")
        
        return {
            "max_age_hours": max_age_hours,
            "stale_lenders": stale_lenders,
            "total_stale": len(stale_lenders)
        }
    
    def get_collection_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get collection statistics for the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        successful_collections = 0
        failed_collections = 0
        total_products = 0
        lender_stats = {}
        
        for key, value in self.metrics.items():
            if key.endswith("_complete") and isinstance(value, dict):
                try:
                    collection_time = datetime.fromisoformat(value["timestamp"])
                    if collection_time >= cutoff_time:
                        lender = value["lender"]
                        
                        if value.get("success", False):
                            successful_collections += 1
                            total_products += value.get("products_collected", 0)
                        else:
                            failed_collections += 1
                        
                        # Track per-lender stats
                        if lender not in lender_stats:
                            lender_stats[lender] = {
                                "successful": 0,
                                "failed": 0,
                                "total_products": 0
                            }
                        
                        if value.get("success", False):
                            lender_stats[lender]["successful"] += 1
                            lender_stats[lender]["total_products"] += value.get("products_collected", 0)
                        else:
                            lender_stats[lender]["failed"] += 1
                            
                except:
                    continue
        
        return {
            "period_hours": hours,
            "successful_collections": successful_collections,
            "failed_collections": failed_collections,
            "total_products_collected": total_products,
            "success_rate": successful_collections / (successful_collections + failed_collections) if (successful_collections + failed_collections) > 0 else 0,
            "lender_breakdown": lender_stats
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        # Check data freshness
        freshness_check = self.check_data_freshness()
        
        # Get recent collection stats
        recent_stats = self.get_collection_stats(hours=24)
        
        # Determine overall health
        health_status = "healthy"
        if recent_stats["success_rate"] < 0.8:  # Less than 80% success rate
            health_status = "degraded"
        if freshness_check["total_stale"] > 0:
            health_status = "unhealthy"
        if recent_stats["failed_collections"] > recent_stats["successful_collections"]:
            health_status = "critical"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "data_freshness": freshness_check,
            "collection_stats": recent_stats,
            "active_alerts": len(self.alerts),
            "recent_alerts": self.alerts[-5:] if self.alerts else []
        }
    
    def _create_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Create a new alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        logger.warning(f"Alert created: {alert_type} - {message}")
    
    def clear_old_alerts(self, days: int = 7):
        """Clear alerts older than specified days."""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        filtered_alerts = []
        for alert in self.alerts:
            try:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if alert_time >= cutoff_time:
                    filtered_alerts.append(alert)
            except:
                continue
        
        self.alerts = filtered_alerts
        logger.info(f"Cleared old alerts, keeping {len(self.alerts)} recent alerts")
    
    def export_metrics(self, file_path: Optional[str] = None) -> str:
        """Export metrics to JSON file."""
        if not file_path:
            file_path = f"metrics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "alerts": self.alerts,
            "system_health": self.get_system_health()
        }
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Metrics exported to {file_path}")
        return file_path
