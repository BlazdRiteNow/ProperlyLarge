from flask import Flask, request, send_file, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import tempfile
import zipfile
from main import process_stl
import gc  # Garbage collection
import shutil

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/process', methods=['POST'])
def process_stl_endpoint():
    temp_dir = None
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

        # Create temporary directory manually instead of using context manager
        temp_dir = tempfile.mkdtemp()
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
            
            # Process STL - this now returns the output directory path
            output_dir = process_stl(config)
            
            # Create zip file of results
            zip_path = os.path.join(temp_dir, "results.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.stl'):
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, output_dir)
                            zipf.write(file_path, arcname)
            
            response = send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name='processed_stl.zip'
            )
            
            # Clean up after sending file
            @response.call_on_close
            def cleanup():
                try:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    print(f"Cleanup error: {e}")
                gc.collect()
            
            return response
                
        except Exception as e:
            # Clean up on error
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            gc.collect()
            raise
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 