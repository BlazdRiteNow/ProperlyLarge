from flask import Flask, request, send_file, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import tempfile
import zipfile
from main import process_stl
import gc  # Garbage collection
import shutil
import trimesh

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

def validate_stl_manifold(stl_path):
    """
    Validates STL file for non-manifold edges and returns a tuple of
    (is_valid, error_message)
    """
    try:
        mesh = trimesh.load_mesh(stl_path)
        
        # Check if the mesh has non-manifold edges
        if not mesh.is_watertight:
            # Get the specific non-manifold edges
            non_manifold_edges = mesh.edges_unique[mesh.edges_unique_length > 2]
            return False, f"Model contains {len(non_manifold_edges)} non-manifold edges"
            
        # Check if the mesh has consistent face normals
        if not mesh.is_volume:
            return False, "Model has inconsistent face normals"
            
        return True, None
        
    except Exception as e:
        return False, f"Error validating mesh: {str(e)}"

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
            
            # Validate and warn, but continue processing
            is_valid, error_message = validate_stl_manifold(input_path)
            warning_message = None
            if not is_valid:
                warning_message = {
                    "warning": "Non-manifold edges detected",
                    "details": error_message,
                    "action_needed": "You may need to repair this model in your slicing software before printing"
                }
                print(f"Processing continuing with warning: {error_message}")
            
            # Continue with normal processing
            config = {
                "target_height_feet": target_height_feet,
                "printer_bed_size": 300,
                "safety_margin": 5,
                "input_file": input_path,
                "height_axis": height_axis,
                "output_base_dir": temp_dir
            }
            
            # Process STL
            output_dir = process_stl(config)
            
            # Add warning to zip if there was one
            if warning_message:
                warning_path = os.path.join(temp_dir, "processing_warning.txt")
                with open(warning_path, 'w') as f:
                    f.write(str(warning_message))
                
            # Create zip file of results
            zip_path = os.path.join(temp_dir, "results.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.endswith('.stl'):
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, output_dir)
                            zipf.write(file_path, arcname)
                # Include warning file if it exists
                if warning_message:
                    zipf.write(warning_path, "processing_warning.txt")
            
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

def repair_stl_mesh(stl_path, output_path=None):
    """
    Attempts to repair an STL mesh using various methods.
    Returns (success, message, repaired_mesh)
    """
    try:
        mesh = trimesh.load_mesh(stl_path)
        original_vertices = len(mesh.vertices)
        
        # Method 1: Fill holes and remove duplicate/degenerate faces
        mesh.fill_holes()
        mesh.remove_degenerate_faces()
        mesh.remove_duplicate_faces()
        
        # Method 2: Merge nearby vertices that might be causing non-manifold edges
        mesh.merge_vertices(merge_tolerance=0.0001)  # Adjust tolerance as needed
        
        # Method 3: Fix normals
        mesh.fix_normals()
        
        # Optional: Process only the largest component if there are disconnected parts
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda m: len(m.faces))
        
        # Verify if repairs worked
        is_watertight = mesh.is_watertight
        message = (f"Processed mesh: {len(mesh.vertices)} vertices "
                  f"(originally {original_vertices}). "
                  f"Watertight: {is_watertight}")
        
        if output_path:
            mesh.export(output_path)
            
        return is_watertight, message, mesh
        
    except Exception as e:
        return False, f"Repair failed: {str(e)}", None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 