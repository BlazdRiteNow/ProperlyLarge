import trimesh
import numpy as np
import os
import shutil
from scipy.spatial import cKDTree

def scale_stl_to_height(input_file, target_height_mm=609.6):
    mesh = trimesh.load_mesh(input_file)
    current_height = mesh.bounds[1][2] - mesh.bounds[0][2]
    scale_factor = target_height_mm / current_height
    mesh.apply_scale(scale_factor)
    return mesh

def find_detail_regions(mesh, resolution=50):
    try:
        # Create a grid of points
        bounds = mesh.bounds
        x = np.linspace(bounds[0][0], bounds[1][0], resolution)
        y = np.linspace(bounds[0][1], bounds[1][1], resolution)
        z = np.linspace(bounds[0][2], bounds[1][2], resolution)
        
        # Calculate vertex density
        detail_scores = np.zeros((resolution, resolution, resolution))
        tree = cKDTree(mesh.vertices)
        
        # Sample fewer points for performance
        x_sample = x[::2]
        y_sample = y[::2]
        z_sample = z[::2]
        
        for i, xi in enumerate(x_sample):
            for j, yi in enumerate(y_sample):
                for k, zi in enumerate(z_sample):
                    point = np.array([xi, yi, zi])
                    nearby_vertices = tree.query_ball_point(point, r=20)
                    if nearby_vertices:
                        detail_scores[i*2,j*2,k*2] = len(nearby_vertices)
        
        return detail_scores, (x, y, z)
    except Exception as e:
        print(f"Error in find_detail_regions: {str(e)}")
        return np.zeros((resolution, resolution, resolution)), (x, y, z)

def split_mesh(mesh, output_dir, piece_number=0, max_size=300):
    try:
        # Check if piece fits within build volume
        dims = mesh.bounds[1] - mesh.bounds[0]
        if all(d <= max_size for d in dims):
            filename = os.path.join(output_dir, f'piece_{piece_number}.stl')
            mesh.export(filename)
            print(f"Saved {filename} with dimensions {dims}")
            return piece_number + 1
        
        # Find largest dimension
        largest_dim = max(dims)
        axis = np.argmax(dims)
        
        # Simple midpoint split for now
        mid_point = (mesh.bounds[1][axis] + mesh.bounds[0][axis]) / 2
        
        # Create cutting plane
        plane_normal = np.zeros(3)
        plane_normal[axis] = 1
        plane_origin = np.zeros(3)
        plane_origin[axis] = mid_point
        
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
        
        # Process both halves
        if first_half is not None:
            piece_number = split_mesh(first_half, output_dir, piece_number, max_size)
        
        if second_half is not None:
            piece_number = split_mesh(second_half, output_dir, piece_number, max_size)
        
        return piece_number
        
    except Exception as e:
        print(f"Error in split_mesh: {str(e)}")
        # If we encounter an error, try to save the current piece
        try:
            if mesh is not None:
                filename = os.path.join(output_dir, f'piece_{piece_number}_error.stl')
                mesh.export(filename)
                print(f"Saved error piece to {filename}")
        except:
            pass
        return piece_number + 1

def main():
    try:
        # Create output directory
        output_dir = "baby_yoda_parts"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        # Load and scale model
        input_file = "Baby_Yoda_Christmas_Ornament_-_Full.stl"
        print("Loading and scaling model...")
        scaled_model = scale_stl_to_height(input_file)
        
        print("Starting mesh splitting...")
        split_mesh(scaled_model, output_dir, max_size=300)
        print("Splitting complete!")
        
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
