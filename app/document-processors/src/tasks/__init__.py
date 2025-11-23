#!/usr/bin/env python3
"""
Tasks package - auto-discovery of all task modules
"""
from tasks.celery import app

# Import all task modules to register them with Celery
from tasks import word_tasks
from tasks import pptx_tasks
from tasks import pdf_tasks
from tasks import txt_tasks
from tasks import delete_tasks
from tasks import passthrough_tasks

__all__ = ['app', 'word_tasks', 'pptx_tasks', 'pdf_tasks', 'txt_tasks', 'delete_tasks', 'passthrough_tasks']
