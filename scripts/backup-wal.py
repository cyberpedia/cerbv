#!/usr/bin/env python3
"""
Cerberus CTF Platform - WAL-G Backup Implementation
Description: Continuous WAL archiving and base backup management
Version: 1.0.0
"""

import os
import sys
import json
import logging
import subprocess
import hashlib
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import argparse

# Configuration
LOG_FILE = "/var/log/cerberus/backup.log"
CONFIG_FILE = "/opt/cerberus/walg.yml"
BACKUP_RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
BACKUP_SCHEDULE = os.getenv("BACKUP_SCHEDULE", "0 2 * * *")  # Daily at 2 AM UTC

# Setup logging
def setup_logging():
    """Configure logging for backup operations."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class WALGBackupManager:
    """Manages PostgreSQL backups using WAL-G."""
    
    def __init__(self):
        self.pg_host = os.getenv("PGHOST", "localhost")
        self.pg_port = os.getenv("PGPORT", "5432")
        self.pg_database = os.getenv("PGDATABASE", "cerberus")
        self.pg_user = os.getenv("PGUSER", "cerberus_admin")
        self.pg_password = os.getenv("PGPASSWORD", "")
        
        # S3/MinIO configuration
        self.s3_prefix = os.getenv("WALG_S3_PREFIX", "s3://postgres-wal/wal")
        self.s3_access_key = os.getenv("WALG_S3_ACCESS_KEY", "")
        self.s3_secret_key = os.getenv("WALG_S3_SECRET_KEY", "")
        self.s3_endpoint = os.getenv("WALG_S3_ENDPOINT", "http://minio:9000")
        self.compression = os.getenv("WALG_COMPRESSION_METHOD", "lz4")
        
        self.env = self._setup_environment()
    
    def _setup_environment(self) -> Dict[str, str]:
        """Setup environment variables for WAL-G."""
        env = os.environ.copy()
        
        # WAL-G specific variables
        env["WALG_S3_PREFIX"] = self.s3_prefix
        env["AWS_ACCESS_KEY_ID"] = self.s3_access_key
        env["AWS_SECRET_ACCESS_KEY"] = self.s3_secret_key
        env["AWS_ENDPOINT"] = self.s3_endpoint
        env["AWS_S3_FORCE_PATH_STYLE"] = "true"
        env["WALG_COMPRESSION_METHOD"] = self.compression
        env["WALG_DELTA_MAX_STEPS"] = "7"
        env["WALG_UPLOAD_CONCURRENCY"] = "4"
        env["WALG_DOWNLOAD_CONCURRENCY"] = "4"
        env["WALG_UPLOAD_DISK_CONCURRENCY"] = "4"
        env["WALG_PREVENT_WAL_OVERWRITE"] = "1"
        env["WALG_VERIFY_PAGE_CHECKSUMS"] = "1"
        
        # PostgreSQL connection
        env["PGHOST"] = self.pg_host
        env["PGPORT"] = self.pg_port
        env["PGDATABASE"] = self.pg_database
        env["PGUSER"] = self.pg_user
        env["PGPASSWORD"] = self.pg_password
        
        return env
    
    def check_walg_installed(self) -> bool:
        """Check if WAL-G binary is available."""
        try:
            result = subprocess.run(
                ["wal-g", "version"],
                capture_output=True,
                text=True,
                env=self.env
            )
            return result.returncode == 0
        except FileNotFoundError:
            logger.error("WAL-G binary not found. Install with: https://github.com/wal-g/wal-g")
            return False
    
    def check_postgres_connection(self) -> bool:
        """Verify PostgreSQL connection."""
        try:
            result = subprocess.run(
                ["pg_isready", "-h", self.pg_host, "-p", self.pg_port, "-U", self.pg_user],
                capture_output=True,
                text=True,
                env=self.env
            )
            if result.returncode == 0:
                logger.info(f"PostgreSQL connection successful: {self.pg_host}:{self.pg_port}")
                return True
            else:
                logger.error(f"PostgreSQL connection failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error checking PostgreSQL connection: {e}")
            return False
    
    def check_s3_connection(self) -> bool:
        """Verify S3/MinIO connection."""
        try:
            result = subprocess.run(
                ["wal-g", "st", "ls"],
                capture_output=True,
                text=True,
                env=self.env
            )
            if result.returncode == 0:
                logger.info("S3/MinIO connection successful")
                return True
            else:
                logger.error(f"S3/MinIO connection failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error checking S3 connection: {e}")
            return False
    
    def create_base_backup(self) -> bool:
        """Create a new base backup."""
        logger.info("Starting base backup...")
        
        try:
            result = subprocess.run(
                ["wal-g", "backup-push", "/var/lib/postgresql/data"],
                capture_output=True,
                text=True,
                env=self.env,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logger.info("Base backup completed successfully")
                return True
            else:
                logger.error(f"Base backup failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("Base backup timed out after 1 hour")
            return False
        except Exception as e:
            logger.error(f"Error during base backup: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        try:
            result = subprocess.run(
                ["wal-g", "backup-list", "--json"],
                capture_output=True,
                text=True,
                env=self.env
            )
            
            if result.returncode == 0:
                backups = json.loads(result.stdout)
                logger.info(f"Found {len(backups)} backups")
                return backups
            else:
                logger.error(f"Failed to list backups: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []
    
    def delete_old_backups(self, retention_days: int = None) -> bool:
        """Delete backups older than retention period."""
        if retention_days is None:
            retention_days = BACKUP_RETENTION_DAYS
        
        logger.info(f"Cleaning up backups older than {retention_days} days...")
        
        try:
            result = subprocess.run(
                ["wal-g", "delete", "--confirm", "--before", f"{retention_days}D"],
                capture_output=True,
                text=True,
                env=self.env
            )
            
            if result.returncode == 0:
                logger.info("Old backups cleaned up successfully")
                return True
            else:
                logger.error(f"Failed to delete old backups: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error deleting old backups: {e}")
            return False
    
    def verify_backup(self, backup_name: str = None) -> bool:
        """Verify backup integrity."""
        logger.info("Verifying backup integrity...")
        
        try:
            if backup_name:
                result = subprocess.run(
                    ["wal-g", "backup-fetch", "/tmp/backup-verify", backup_name],
                    capture_output=True,
                    text=True,
                    env=self.env,
                    timeout=600
                )
            else:
                # Verify latest backup
                result = subprocess.run(
                    ["wal-g", "backup-verify"],
                    capture_output=True,
                    text=True,
                    env=self.env,
                    timeout=600
                )
            
            if result.returncode == 0:
                logger.info("Backup verification successful")
                return True
            else:
                logger.error(f"Backup verification failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error verifying backup: {e}")
            return False
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup status."""
        backups = self.list_backups()
        
        if not backups:
            return {
                "status": "no_backups",
                "last_backup": None,
                "total_backups": 0
            }
        
        # Sort by time (newest first)
        backups.sort(key=lambda x: x.get("time", ""), reverse=True)
        latest = backups[0]
        
        return {
            "status": "ok",
            "last_backup": latest.get("time"),
            "last_backup_size": latest.get("compressed_size", 0),
            "total_backups": len(backups),
            "oldest_backup": backups[-1].get("time") if backups else None
        }
    
    def run_backup_cycle(self) -> bool:
        """Run a complete backup cycle."""
        logger.info("=" * 50)
        logger.info("Starting backup cycle")
        logger.info("=" * 50)
        
        # Pre-flight checks
        if not self.check_postgres_connection():
            logger.error("PostgreSQL connection check failed")
            return False
        
        if not self.check_s3_connection():
            logger.error("S3/MinIO connection check failed")
            return False
        
        # Create backup
        if not self.create_base_backup():
            logger.error("Base backup creation failed")
            return False
        
        # Clean up old backups
        if not self.delete_old_backups():
            logger.warning("Failed to clean up old backups (non-fatal)")
        
        # Get status
        status = self.get_backup_status()
        logger.info(f"Backup status: {json.dumps(status, indent=2)}")
        
        logger.info("=" * 50)
        logger.info("Backup cycle completed successfully")
        logger.info("=" * 50)
        
        return True


class BackupScheduler:
    """Schedules backup operations."""
    
    def __init__(self, manager: WALGBackupManager):
        self.manager = manager
        self.running = False
    
    def parse_schedule(self, schedule: str) -> int:
        """Parse cron-like schedule and return seconds until next run."""
        # Simplified: run daily at specified time
        # Format: "MIN HOUR * * *"
        parts = schedule.split()
        if len(parts) >= 2:
            minute = int(parts[0])
            hour = int(parts[1])
            
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return int((next_run - now).total_seconds())
        
        return 86400  # Default: 24 hours
    
    def run(self):
        """Run scheduler loop."""
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info(f"Backup scheduler started (schedule: {BACKUP_SCHEDULE})")
        
        while self.running:
            try:
                # Run backup cycle
                self.manager.run_backup_cycle()
                
                # Calculate sleep time
                sleep_seconds = self.parse_schedule(BACKUP_SCHEDULE)
                logger.info(f"Next backup in {sleep_seconds} seconds")
                
                # Sleep with interrupt checking
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in backup cycle: {e}")
                time.sleep(300)  # Wait 5 minutes on error
        
        logger.info("Backup scheduler stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Cerberus WAL-G Backup Manager")
    parser.add_argument("--backup", action="store_true", help="Run single backup")
    parser.add_argument("--list", action="store_true", help="List backups")
    parser.add_argument("--verify", metavar="BACKUP", help="Verify specific backup")
    parser.add_argument("--clean", action="store_true", help="Clean old backups")
    parser.add_argument("--status", action="store_true", help="Show backup status")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--retention", type=int, default=30, help="Retention days")
    
    args = parser.parse_args()
    
    manager = WALGBackupManager()
    
    # Check WAL-G availability
    if not manager.check_walg_installed():
        logger.error("WAL-G not installed. Please install WAL-G first.")
        sys.exit(1)
    
    if args.backup:
        success = manager.run_backup_cycle()
        sys.exit(0 if success else 1)
    
    elif args.list:
        backups = manager.list_backups()
        print(json.dumps(backups, indent=2))
    
    elif args.verify:
        success = manager.verify_backup(args.verify)
        sys.exit(0 if success else 1)
    
    elif args.clean:
        success = manager.delete_old_backups(args.retention)
        sys.exit(0 if success else 1)
    
    elif args.status:
        status = manager.get_backup_status()
        print(json.dumps(status, indent=2))
    
    elif args.daemon:
        scheduler = BackupScheduler(manager)
        scheduler.run()
    
    else:
        # Default: run single backup
        success = manager.run_backup_cycle()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
