from flask import Flask, render_template_string, jsonify, request
import json
import os
from typing import Dict, Any

app = Flask(__name__)

class PDFData:
    def __init__(self, json_path: str = "output.json"):
        self.json_path = json_path
        self.data = None
        self.load_data()
    
    def load_data(self):
        """Load the JSON data from file."""
        try:
            with open(self.json_path, 'r') as f:
                self.data = json.load(f)
            print(f"✓ Loaded PDF data: {self.data.get('pdf_path', 'Unknown')}")
            print(f"✓ Total pages: {self.data.get('pages_processed', 0)}")
        except FileNotFoundError:
            print(f"❌ Error: {self.json_path} not found")
            self.data = None
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON: {e}")
            self.data = None
    
    def get_page_data(self, page_num: int) -> Dict[str, Any]:
        """Get data for a specific page."""
        if not self.data or 'pages' not in self.data:
            return {}
        
        for page in self.data['pages']:
            if page['page_number'] == page_num:
                return page
        return {}
    
    def get_total_pages(self) -> int:
        """Get total number of pages."""
        return self.data.get('pages_processed', 0) if self.data else 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.data:
            return {}
        
        summary = {
            'pdf_path': self.data.get('pdf_path', 'Unknown'),
            'pages_processed': self.data.get('pages_processed', 0),
            'pymupdf_total_chars': 0,
            'pdfplumber_total_chars': 0,
            'camelot_total_chars': 0
        }
        
        if 'summary' in self.data:
            summary.update(self.data['summary'])
        
        return summary

# Initialize PDF data
pdf_data = PDFData()

# HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Extraction Viewer</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2em;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .navigation {
            background: #f8f9fa;
            padding: 15px;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .nav-buttons {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: #007bff;
            color: white;
        }
        .btn-primary:hover {
            background: #0056b3;
        }
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background: #545b62;
        }
        .page-input {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 5px;
            width: 80px;
            text-align: center;
        }
        .page-info {
            font-weight: bold;
            color: #495057;
        }
        .content {
            padding: 20px;
        }
        .extraction-section {
            margin-bottom: 30px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }
        .extraction-header {
            padding: 15px;
            font-weight: bold;
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .pymupdf-header {
            background: #28a745;
        }
        .pdfplumber-header {
            background: #17a2b8;
        }
        .camelot-header {
            background: #fd7e14;
        }
        .extraction-content {
            padding: 20px;
            background: #f8f9fa;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.4;
            max-height: 400px;
            overflow-y: auto;
            border-top: 1px solid #dee2e6;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }
        .summary-card h3 {
            margin: 0 0 10px 0;
            color: #495057;
        }
        .summary-card .number {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        .comparison-view {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        .comparison-section {
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        @media (max-width: 768px) {
            .navigation {
                flex-direction: column;
                gap: 10px;
            }
            .comparison-view {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 PDF Extraction Viewer</h1>
            <p id="pdf-path">Loading...</p>
        </div>
        
        <div class="navigation">
            <div class="nav-buttons">
                <button class="btn btn-secondary" onclick="previousPage()">← Previous</button>
                <button class="btn btn-secondary" onclick="nextPage()">Next →</button>
                <input type="number" class="page-input" id="page-input" min="1" onchange="goToPage(this.value)">
                <button class="btn btn-primary" onclick="goToPage(document.getElementById('page-input').value)">Go</button>
            </div>
            <div class="page-info" id="page-info">Page 1 of 1</div>
            <div class="nav-buttons">
                <button class="btn btn-primary" onclick="showSummary()">📊 Summary</button>
                <button class="btn btn-primary" onclick="toggleComparison()">🔍 Compare</button>
            </div>
        </div>
        
        <div class="content">
            <div id="summary-view" style="display: none;">
                <h2>📊 Extraction Summary</h2>
                <div class="summary-grid" id="summary-grid">
                    <!-- Summary cards will be populated here -->
                </div>
            </div>
            
            <div id="page-view">
                <div id="page-content">
                    <div class="loading">Loading page data...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentPage = 1;
        let totalPages = 1;
        let comparisonMode = false;
        let pdfData = null;

        // Initialize the viewer
        async function init() {
            try {
                const response = await fetch('/api/summary');
                const summary = await response.json();
                
                if (summary.error) {
                    showError(summary.error);
                    return;
                }
                
                totalPages = summary.pages_processed;
                document.getElementById('pdf-path').textContent = summary.pdf_path;
                document.getElementById('page-input').max = totalPages;
                
                updatePageInfo();
                loadPage(1);
                loadSummary();
            } catch (error) {
                showError('Failed to load PDF data: ' + error.message);
            }
        }

        async function loadPage(pageNum) {
            currentPage = pageNum;
            updatePageInfo();
            
            try {
                const response = await fetch(`/api/page/${pageNum}`);
                const pageData = await response.json();
                
                if (pageData.error) {
                    showError(pageData.error);
                    return;
                }
                
                displayPage(pageData);
            } catch (error) {
                showError('Failed to load page: ' + error.message);
            }
        }

        async function loadSummary() {
            try {
                const response = await fetch('/api/summary');
                const summary = await response.json();
                
                if (summary.error) {
                    return;
                }
                
                displaySummary(summary);
            } catch (error) {
                console.error('Failed to load summary:', error);
            }
        }

        function displayPage(pageData) {
            const content = document.getElementById('page-content');
            
            if (comparisonMode) {
                content.innerHTML = `
                    <div class="comparison-view">
                        <div class="comparison-section">
                            <div class="extraction-header pymupdf-header">
                                🔍 PyMuPDF
                                <span>${pageData.pymupdf_text ? pageData.pymupdf_text.length : 0} chars</span>
                            </div>
                            <div class="extraction-content">${pageData.pymupdf_text || 'No text extracted'}</div>
                        </div>
                        <div class="comparison-section">
                            <div class="extraction-header pdfplumber-header">
                                📊 pdfplumber
                                <span>${pageData.pdfplumber_text ? pageData.pdfplumber_text.length : 0} chars</span>
                            </div>
                            <div class="extraction-content">${pageData.pdfplumber_text || 'No text extracted'}</div>
                        </div>
                        <div class="comparison-section">
                            <div class="extraction-header camelot-header">
                                📋 Camelot
                                <span>${pageData.camelot_text ? pageData.camelot_text.length : 0} chars</span>
                            </div>
                            <div class="extraction-content">${pageData.camelot_text || 'No tables found'}</div>
                        </div>
                    </div>
                `;
            } else {
                content.innerHTML = `
                    <div class="extraction-section">
                        <div class="extraction-header pymupdf-header">
                            🔍 PyMuPDF Extraction
                            <span>${pageData.pymupdf_text ? pageData.pymupdf_text.length : 0} characters</span>
                        </div>
                        <div class="extraction-content">${pageData.pymupdf_text || 'No text extracted'}</div>
                    </div>
                    
                    <div class="extraction-section">
                        <div class="extraction-header pdfplumber-header">
                            📊 pdfplumber Extraction
                            <span>${pageData.pdfplumber_text ? pageData.pdfplumber_text.length : 0} characters</span>
                        </div>
                        <div class="extraction-content">${pageData.pdfplumber_text || 'No text extracted'}</div>
                    </div>
                    
                    <div class="extraction-section">
                        <div class="extraction-header camelot-header">
                            📋 Camelot Extraction
                            <span>${pageData.camelot_text ? pageData.camelot_text.length : 0} characters</span>
                        </div>
                        <div class="extraction-content">${pageData.camelot_text || 'No tables found'}</div>
                    </div>
                `;
            }
        }

        function displaySummary(summary) {
            const summaryGrid = document.getElementById('summary-grid');
            summaryGrid.innerHTML = `
                <div class="summary-card">
                    <h3>📄 Total Pages</h3>
                    <div class="number">${summary.pages_processed}</div>
                </div>
                <div class="summary-card">
                    <h3>🔍 PyMuPDF Characters</h3>
                    <div class="number">${summary.pymupdf_total_chars.toLocaleString()}</div>
                </div>
                <div class="summary-card">
                    <h3>📊 pdfplumber Characters</h3>
                    <div class="number">${summary.pdfplumber_total_chars.toLocaleString()}</div>
                </div>
                <div class="summary-card">
                    <h3>📋 Camelot Characters</h3>
                    <div class="number">${summary.camelot_total_chars.toLocaleString()}</div>
                </div>
            `;
        }

        function updatePageInfo() {
            document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
            document.getElementById('page-input').value = currentPage;
        }

        function previousPage() {
            if (currentPage > 1) {
                loadPage(currentPage - 1);
            }
        }

        function nextPage() {
            if (currentPage < totalPages) {
                loadPage(currentPage + 1);
            }
        }

        function goToPage(pageNum) {
            const num = parseInt(pageNum);
            if (num >= 1 && num <= totalPages) {
                loadPage(num);
            }
        }

        function showSummary() {
            const summaryView = document.getElementById('summary-view');
            const pageView = document.getElementById('page-view');
            
            if (summaryView.style.display === 'none') {
                summaryView.style.display = 'block';
                pageView.style.display = 'none';
            } else {
                summaryView.style.display = 'none';
                pageView.style.display = 'block';
            }
        }

        function toggleComparison() {
            comparisonMode = !comparisonMode;
            loadPage(currentPage);
        }

        function showError(message) {
            document.getElementById('page-content').innerHTML = `
                <div class="error">
                    ❌ Error: ${message}
                </div>
            `;
        }

        // Initialize when page loads
        window.onload = init;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/summary')
def get_summary():
    """Get summary statistics."""
    if not pdf_data.data:
        return jsonify({'error': 'No PDF data loaded'})
    
    return jsonify(pdf_data.get_summary())

@app.route('/api/page/<int:page_num>')
def get_page(page_num):
    """Get data for a specific page."""
    if not pdf_data.data:
        return jsonify({'error': 'No PDF data loaded'})
    
    page_data = pdf_data.get_page_data(page_num)
    if not page_data:
        return jsonify({'error': f'Page {page_num} not found'})
    
    return jsonify(page_data)

@app.route('/api/reload')
def reload_data():
    """Reload the PDF data from file."""
    pdf_data.load_data()
    if pdf_data.data:
        return jsonify({'success': True, 'message': 'Data reloaded successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to reload data'})

def main():
    """Main function to run the web server."""
    import sys
    
    # Check if custom JSON path is provided
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        global pdf_data
        pdf_data = PDFData(json_path)
    
    if not pdf_data.data:
        print("❌ Failed to load PDF data")
        print("Make sure 'output.json' exists in the current directory")
        return
    
    print("🚀 Starting PDF Viewer Server...")
    print(f"📁 Loaded: {pdf_data.data.get('pdf_path', 'Unknown')}")
    print(f"📄 Pages: {pdf_data.get_total_pages()}")
    print("🌐 Open your browser to: http://localhost:4000")
    
    app.run(debug=True, host='0.0.0.0', port=4000)

if __name__ == "__main__":
    main() 