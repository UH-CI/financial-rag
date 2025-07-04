#!/usr/bin/env python3
"""
Simple HTTP server to display the PDF dual extraction viewer
"""

import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

def serve_viewer(port=8080, auto_open=True):
    """
    Start a local HTTP server to serve the HTML viewer
    
    Args:
        port (int): Port to serve on (default: 8080)
        auto_open (bool): Whether to automatically open browser (default: True)
    """
    
    # Get the directory of this script
    script_dir = Path(__file__).parent
    
    # Check if required files exist
    html_file = script_dir / "view_dual_extraction.html"
    json_file = script_dir / "HB300__dual_extraction.json"
    
    if not html_file.exists():
        print(f"❌ Error: {html_file} not found!")
        return
    
    if not json_file.exists():
        print(f"❌ Error: {json_file} not found!")
        return
    
    # Change to the script directory
    os.chdir(script_dir)
    
    # Create server
    Handler = http.server.SimpleHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            url = f"http://localhost:{port}/view_dual_extraction.html"
            
            print(f"🚀 Starting server at {url}")
            print(f"📁 Serving files from: {script_dir}")
            print(f"🔍 Found files:")
            print(f"   ✅ {html_file.name}")
            print(f"   ✅ {json_file.name}")
            print(f"\n📖 Open in browser: {url}")
            print(f"⏹️  Press Ctrl+C to stop the server")
            
            # Auto-open browser
            if auto_open:
                print(f"🌐 Opening browser...")
                webbrowser.open(url)
            
            # Start serving
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n🛑 Server stopped")
    except OSError as e:
        if e.errno == 48:  # Port already in use
            print(f"❌ Port {port} is already in use. Try a different port:")
            print(f"   python serve_viewer.py --port 8081")
        else:
            print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Serve PDF dual extraction viewer")
    parser.add_argument("--port", "-p", type=int, default=8080, 
                       help="Port to serve on (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", 
                       help="Don't automatically open browser")
    
    args = parser.parse_args()
    
    serve_viewer(port=args.port, auto_open=not args.no_browser) 