import trimesh
import numpy as np
import os
import shutil

def scale_stl_to_height(input_file, target_height_mm=609.6):  # 2 feet in mm
    mesh = trimesh.load_mesh(input_file)
    current_height = mesh.bounds[1][2] - mesh.bounds[0][2]
    scale_factor = target_height_mm / current_height
    mesh.apply_scale(scale_factor)
    return mesh

def get_largest_dimension(mesh):
    dims = mesh.bounds[1] - mesh.bounds[0]
    largest_dim = max(dims)
    axis = np.argmax(dims)
    return largest_dim, axis

def split_mesh(mesh, output_dir, piece_number=0, max_size=300):
    # Check if piece fits within build volume
    dims = mesh.bounds[1] - mesh.bounds[0]
    if all(d <= max_size for d in dims):
        # If it fits, save it
        filename = os.path.join(output_dir, f'piece_{piece_number}.stl')
        mesh.export(filename)
        print(f"Saved {filename} with dimensions {dims}")
        return piece_number + 1
    
    # If it doesn't fit, split along largest dimension
    largest_dim, axis = get_largest_dimension(mesh)
    
    # Create cutting plane at midpoint of largest dimension
    mid_point = (mesh.bounds[1][axis] + mesh.bounds[0][axis]) / 2
    plane_normal = np.zeros(3)
    plane_normal[axis] = 1
    plane_origin = np.zeros(3)
    plane_origin[axis] = mid_point
    
    try:
        # Split the mesh
        first_half = mesh.slice_plane(
            plane_origin=plane_origin,
            plane_normal=plane_normal,
            cap=True
        )
        
        second_half = mesh.slice_plane(
            plane_origin=plane_origin,
            plane_normal=[-x for x in plane_normal],
            cap=True
        )
        
        # Recursively split each half if needed
        if first_half is not None:
            piece_number = split_mesh(first_half, output_dir, piece_number, max_size)
        
        if second_half is not None:
            piece_number = split_mesh(second_half, output_dir, piece_number, max_size)
            
        return piece_number
        
    except Exception as e:
        print(f"Error splitting mesh: {str(e)}")
        return piece_number

def main():
    # Create output directory (clean if exists)
    output_dir = "baby_yoda_parts"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    input_file = "Baby_Yoda_Christmas_Ornament_-_Full.stl"
    scaled_model = scale_stl_to_height(input_file)
    
    # Split model into printable pieces
    split_mesh(scaled_model, output_dir, max_size=300)

if __name__ == "__main__":
    main()
