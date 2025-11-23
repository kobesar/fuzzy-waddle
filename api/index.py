"""
Vercel Serverless Function Entry Point
FastAPI adapter for Vercel
"""

from fastapi import FastAPI
from mangum import Mangum
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.main import app

# Wrap FastAPI app for Vercel
handler = Mangum(app)
