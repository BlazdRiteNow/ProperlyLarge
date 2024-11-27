from flask import Flask, request, send_file, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import tempfile
import zipfile
from main import process_stl
import gc  # Garbage collection

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/process', methods=['POST'])
def process_stl_endpoint():
    try:
        # Force garbage collection before processing
        gc.collect()
        
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.stl'):
            return jsonify({"error": "File must be STL format"}), 400
            
        # Get file size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        # Limit file size (e.g., 50MB)
        if size > 50 * 1024 * 1024:  # 50MB in bytes
            return jsonify({"error": "File too large"}), 400

        # Process in chunks using temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                target_height_feet = float(request.form.get('target_height_feet', 2))
                height_axis = request.form.get('height_axis', 'z')
                
                # Save uploaded file
                input_path = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(input_path)
                
                # Configure processing
                config = {
                    "target_height_feet": target_height_feet,
                    "printer_bed_size": 300,
                    "safety_margin": 5,
                    "input_file": input_path,
                    "height_axis": height_axis,
                    "output_base_dir": temp_dir
                }
                
                # Process STL
                process_stl(config)
                
                # Create zip file of results
                zip_path = os.path.join(temp_dir, "results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith('.stl'):
                                file_path = os.path.join(root, file)
                                arcname = os.path.basename(file_path)
                                zipf.write(file_path, arcname)
                
                return send_file(
                    zip_path,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name='processed_stl.zip'
                )
                
            finally:
                # Force cleanup
                gc.collect()
                
    except Exception as e:
        gc.collect()
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 