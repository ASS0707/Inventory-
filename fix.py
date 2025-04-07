import os
import logging
from flask import send_file, render_template

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_file_exists(path):
    """Check if a file exists and log its status"""
    exists = os.path.exists(path)
    logger.info(f"File '{path}': {'EXISTS' if exists else 'MISSING'}")
    return exists

def check_template_exists(template_name, path='templates'):
    """Check if a template exists and log its status"""
    full_path = os.path.join(path, template_name)
    return check_file_exists(full_path)

if __name__ == "__main__":
    logger.info("Starting diagnostics...")
    
    # Check critical files
    check_file_exists('index.html')
    check_file_exists('404.html')
    check_file_exists('500.html')
    check_file_exists('favicon.svg')
    check_file_exists('robots.txt')
    check_file_exists('sitemap.xml')
    check_file_exists('.htaccess')
    
    # Check templates
    check_template_exists('direct_index.html')
    check_template_exists('base.html')
    check_template_exists('errors/404.html', path='templates')
    check_template_exists('errors/500.html', path='templates')
    
    # Check static files
    check_file_exists('static/favicon.svg')
    check_file_exists('static/robots.txt')
    check_file_exists('static/sitemap.xml')
    
    logger.info("Diagnostics completed")
    
    # Test aradate filter implementation
    import datetime
    from app import format_arabic_date
    
    try:
        now = datetime.datetime.now()
        formatted_date = format_arabic_date(now)
        logger.info(f"format_arabic_date filter test: {formatted_date}")
    except Exception as e:
        logger.error(f"Error testing aradate filter: {e}")
    
    # Try to render the direct_index.html template
    from app import app
    try:
        with app.app_context():
            result = render_template('direct_index.html')
            logger.info("Template rendered successfully")
    except Exception as e:
        logger.error(f"Error rendering direct_index.html: {e}")