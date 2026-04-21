#!/usr/bin/env python3
"""
Simple monitoring web interface for job scraper pipeline
"""

import os
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# HTML template for monitoring dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Job Scraper Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .status { display: flex; gap: 20px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex: 1; }
        .metric { font-size: 2em; font-weight: bold; color: #3498db; }
        .label { color: #7f8c8d; font-size: 0.9em; }
        .success { color: #27ae60; }
        .error { color: #e74c3c; }
        .warning { color: #f39c12; }
        .logs { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 0.9em; max-height: 400px; overflow-y: auto; }
        .refresh { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .refresh:hover { background: #2980b9; }
        .timestamp { color: #95a5a6; font-size: 0.8em; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; }
    </style>
    <script>
        function refreshData() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => updateDashboard(data))
                .catch(error => console.error('Error:', error));
        }
        
        function updateDashboard(data) {
            document.getElementById('status').textContent = data.pipeline_status;
            document.getElementById('last_run').textContent = data.last_run || 'Never';
            document.getElementById('jobs_processed').textContent = data.jobs_processed || '0';
            document.getElementById('success_rate').textContent = data.success_rate || '0%';
            document.getElementById('uptime').textContent = data.uptime || '0s';
        }
        
        setInterval(refreshData, 30000); // Refresh every 30 seconds
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Job Scraper Pipeline Monitor</h1>
            <p>Real-time monitoring dashboard for automated job scraping</p>
        </div>
        
        <div class="status">
            <div class="card">
                <div class="metric success" id="status">{{ status.pipeline_status }}</div>
                <div class="label">Pipeline Status</div>
            </div>
            <div class="card">
                <div class="metric" id="jobs_processed">{{ status.jobs_processed }}</div>
                <div class="label">Jobs Processed</div>
            </div>
            <div class="card">
                <div class="metric" id="success_rate">{{ status.success_rate }}</div>
                <div class="label">Success Rate</div>
            </div>
            <div class="card">
                <div class="metric" id="uptime">{{ status.uptime }}</div>
                <div class="label">Uptime</div>
            </div>
        </div>
        
        <div class="card">
            <h3>📊 Recent Activity</h3>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Last Updated</th>
                </tr>
                <tr>
                    <td>Last Run</td>
                    <td id="last_run">{{ status.last_run or 'Never' }}</td>
                    <td class="timestamp">{{ status.last_updated }}</td>
                </tr>
                <tr>
                    <td>URLs Collected</td>
                    <td>{{ status.urls_collected or '0' }}</td>
                    <td class="timestamp">{{ status.last_updated }}</td>
                </tr>
                <tr>
                    <td>Database Records</td>
                    <td>{{ status.db_records or '0' }}</td>
                    <td class="timestamp">{{ status.last_updated }}</td>
                </tr>
            </table>
        </div>
        
        <div class="card">
            <h3>📝 Recent Logs <button class="refresh" onclick="refreshData()">Refresh</button></h3>
            <div class="logs">{{ logs | safe }}</div>
        </div>
        
        <div class="card">
            <h3>⚙️ Configuration</h3>
            <table>
                <tr><td>Environment</td><td>{{ config.environment }}</td></tr>
                <tr><td>Database</td><td>{{ config.database_host }}</td></tr>
                <tr><td>Batch Size</td><td>{{ config.batch_size }}</td></tr>
                <tr><td>Headless Mode</td><td>{{ config.headless }}</td></tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

def get_pipeline_status():
    """Get current pipeline status and metrics"""
    data_dir = Path("/app/data")
    logs_dir = data_dir / "logs"
    
    status = {
        'pipeline_status': 'Unknown',
        'last_run': None,
        'jobs_processed': 0,
        'success_rate': '0%',
        'uptime': get_uptime(),
        'urls_collected': 0,
        'db_records': 0,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Check for recent pipeline log
    pipeline_log = logs_dir / "automated_pipeline.log"
    if pipeline_log.exists():
        try:
            with open(pipeline_log, 'r') as f:
                lines = f.readlines()[-50:]  # Last 50 lines
                
            # Parse log for status
            for line in reversed(lines):
                if "PIPELINE COMPLETED SUCCESSFULLY" in line:
                    status['pipeline_status'] = 'Running'
                    break
                elif "Pipeline failed" in line or "error" in line.lower():
                    status['pipeline_status'] = 'Error'
                    break
            
            # Extract job count if available
            for line in reversed(lines):
                if "jobs scraped" in line:
                    try:
                        count = line.split("jobs scraped")[0].split()[-1]
                        status['jobs_processed'] = int(count)
                    except:
                        pass
                    break
                        
        except Exception as e:
            status['pipeline_status'] = f'Error reading logs: {e}'
    
    # Check output files
    output_dir = data_dir / "output"
    if output_dir.exists():
        csv_file = output_dir / "scraped_jobs.csv"
        if csv_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(csv_file)
                status['db_records'] = len(df)
            except:
                pass
    
    return status

def get_recent_logs(lines=50):
    """Get recent log entries"""
    logs_dir = Path("/app/data/logs")
    pipeline_log = logs_dir / "automated_pipeline.log"
    
    if not pipeline_log.exists():
        return "No logs available yet..."
    
    try:
        with open(pipeline_log, 'r') as f:
            lines = f.readlines()[-lines:]
        
        # Format logs with basic HTML formatting
        formatted_logs = []
        for line in lines:
            line = line.strip()
            if 'ERROR' in line or 'Failed' in line:
                formatted_logs.append(f'<span class="error">{line}</span>')
            elif 'WARNING' in line:
                formatted_logs.append(f'<span class="warning">{line}</span>')
            elif 'completed successfully' in line or 'SUCCESS' in line:
                formatted_logs.append(f'<span class="success">{line}</span>')
            else:
                formatted_logs.append(line)
        
        return '<br>'.join(formatted_logs)
        
    except Exception as e:
        return f"Error reading logs: {e}"

def get_uptime():
    """Get container uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    except:
        return "Unknown"

def get_config():
    """Get configuration info"""
    return {
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'database_host': os.getenv('DB_HOST', 'localhost'),
        'batch_size': os.getenv('SCRAPER_BATCH_SIZE', '10'),
        'headless': os.getenv('SCRAPER_HEADLESS', 'true')
    }

@app.route('/')
def dashboard():
    """Main monitoring dashboard"""
    status = get_pipeline_status()
    logs = get_recent_logs()
    config = get_config()
    
    return render_template_string(DASHBOARD_HTML, 
                                status=status, 
                                logs=logs, 
                                config=config)

@app.route('/api/status')
def api_status():
    """API endpoint for status data"""
    return jsonify(get_pipeline_status())

@app.route('/api/logs')
def api_logs():
    """API endpoint for logs"""
    return {'logs': get_recent_logs()}

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=True)