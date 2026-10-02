import os
import sys

# Add the project root to sys.path so we can import backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect
from backend.models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_models")

def verify_models():
    logger.info("Starting comprehensive model verification (No DB connection required)...")
    
    # 1. Verify that Base has registered models
    registered_tables = list(Base.metadata.tables.keys())
    logger.info(f"Registered tables in MetaData: {registered_tables}")
    
    if not registered_tables:
        logger.error("No tables registered! Models might not be imported correctly in __init__.py")
        sys.exit(1)
        
    expected_tables = [
        "users", "wards", "departments", "civic_cases", "report_signals",
        "evidence_items", "ai_analyses", "work_orders", "verifications",
        "supports", "case_relations", "notifications", "incidents", "audit_events"
    ]
    
    missing_tables = set(expected_tables) - set(registered_tables)
    if missing_tables:
        logger.error(f"Missing expected tables: {missing_tables}")
        sys.exit(1)
        
    # 2. Inspect each model class to ensure relationships and columns are valid
    # In SQLAlchemy, just inspecting the mapper will trigger validation of relationships
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table_name = cls.__tablename__
        logger.info(f"Inspecting model {cls.__name__} (Table: {table_name})")
        
        try:
            inspector = inspect(cls)
            columns = [c.key for c in inspector.columns]
            relationships = [r.key for r in inspector.relationships]
            logger.info(f"  -> Columns: {len(columns)} found")
            logger.info(f"  -> Relationships: {len(relationships)} found")
        except Exception as e:
            logger.error(f"Failed to inspect model {cls.__name__}: {str(e)}")
            sys.exit(1)
            
    logger.info("All models passed static verification successfully! No relationship or mapping errors found.")

if __name__ == "__main__":
    verify_models()
