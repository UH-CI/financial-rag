
import sys
import os
import logging

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import db_manager
from database.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_super_admins():
    logger.info("Starting migration: Fixing super-admin roles...")
    
    with db_manager.get_session() as session:
        # Find all super admins
        super_admins = session.query(User).filter(User.is_super_admin == True).all()
        
        count = 0
        updated_count = 0
        
        for user in super_admins:
            count += 1
            if not user.is_admin:
                logger.info(f"Updating user {user.email} (ID: {user.id}) to be admin as well.")
                user.is_admin = True
                updated_count += 1
            else:
                logger.debug(f"User {user.email} is already admin.")
        
        if updated_count > 0:
            logger.info(f"Committing changes for {updated_count} users...")
            # Session commits automatically on exit of context manager
        else:
            logger.info("No users needed updates.")
            
        logger.info(f"Migration completed. Checked {count} super-admins, updated {updated_count}.")

if __name__ == "__main__":
    try:
        migrate_super_admins()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
