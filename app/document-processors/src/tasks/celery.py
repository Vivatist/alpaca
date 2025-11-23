#!/usr/bin/env python3
"""
Celery app instance and shared imports for all tasks
"""
import os
import sys
from pathlib import Path
from celery import Celery

# Setup shared paths
shared_path = Path(__file__).parent.parent.parent.parent / 'shared'
sys.path.insert(0, str(shared_path / 'logging'))
sys.path.insert(0, '/app/shared/logging')
sys.path.insert(0, str(shared_path / 'config'))
sys.path.insert(0, '/app/shared/config')

# Import shared modules
from alpaca_logger import setup_logger
from config_loader import ConfigLoader

# Celery app instance
app = Celery('alpaca', broker=os.getenv('CELERY_BROKER_URL', 'amqp://admin:alpaca123@rabbitmq:5672//'))

# Load config
config = ConfigLoader.load_full_config()

__all__ = ['app', 'config', 'setup_logger']
