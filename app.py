from flask import Flask, render_template, request, jsonify, send_file
import os
import tempfile
from werkzeug.utils import secure_filename
from main import process_stl
import threading
import time
import zipfile
import logging
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/home/kh1rfan08/mysite/tmp'  # Update with your username
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Create tmp directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Set up logging
logging.basicConfig(
    filename=os.path.join(app.config['UPLOAD_FOLDER'], 'processing.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log_progress(job_id, message):
    """Log a progress message and save it to a job-specific file"""
    logging.info(f"Job {job_id}: {message}")
    log_file = os.path.join(app.config['UPLOAD_FOLDER'], f'progress_{job_id}.txt')
    with open(log_file, 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"{timestamp}: {message}\n")

def process_file_async(filepath, config, job_id):
    try:
        log_progress(job_id, "Starting processing... (This may take 5-10 minutes for large files)")
        
        # Increase timeout to 15 minutes (giving some extra buffer)
        def timeout_handler():
            log_progress(job_id, "Process timed out after 15 minutes")
            raise TimeoutError("Processing took too long")
            
        timer = threading.Timer(900, timeout_handler)  # 15 minutes
        timer.start()
        
        try:
            output_dir = process_stl(config)
            timer.cancel()
        except Exception as e:
            timer.cancel()
            raise e
            
        # Create a zip file of the results
        log_progress(job_id, "Creating zip file of results...")
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], f'result_{job_id}.zip')
        try:
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.stl'):
                            file_path = os.path.join(root, file)
                            arcname = os.path.basename(file_path)
                            zipf.write(file_path, arcname)
                            log_progress(job_id, f"Added {arcname} to zip file")
        except Exception as e:
            log_progress(job_id, f"Error creating zip file: {str(e)}")
            raise
        
        # Cleanup original files
        log_progress(job_id, "Cleaning up temporary files...")
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)
        
        log_progress(job_id, "Processing completed successfully!")
        return True
    except Exception as e:
        error_msg = f"Error in process_file_async: {str(e)}"
        log_progress(job_id, error_msg)
        print(error_msg)  # This will go to the Python Anywhere error logs
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.stl'):
        return jsonify({'error': 'Only STL files are allowed'}), 400

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Generate unique job ID
        job_id = str(int(time.time()))

        # Create config from form data
        config = {
            'target_height_feet': float(request.form.get('height', 2)),
            'printer_bed_size': float(request.form.get('bed_size', 300)),
            'safety_margin': float(request.form.get('margin', 5)),
            'height_axis': request.form.get('axis', 'z'),
            'input_file': filepath,
            'output_base_dir': app.config['UPLOAD_FOLDER']
        }

        # Start processing in background thread
        thread = threading.Thread(
            target=process_file_async,
            args=(filepath, config, job_id)
        )
        thread.start()

        return jsonify({
            'status': 'processing',
            'job_id': job_id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<job_id>')
def check_status(job_id):
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], f'result_{job_id}.zip')
    log_file = os.path.join(app.config['UPLOAD_FOLDER'], f'progress_{job_id}.txt')
    
    # Get progress messages
    messages = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            messages = f.readlines()[-10:]  # Get last 10 messages
    
    if os.path.exists(zip_path):
        return jsonify({
            'status': 'complete',
            'download_url': f'/download/{job_id}',
            'messages': messages
        })
    
    return jsonify({
        'status': 'processing',
        'messages': messages
    })

@app.route('/download/<job_id>')
def download_file(job_id):
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], f'result_{job_id}.zip')
    if os.path.exists(zip_path):
        return send_file(
            zip_path,
            as_attachment=True,
            download_name='processed_stl_files.zip'
        )
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
