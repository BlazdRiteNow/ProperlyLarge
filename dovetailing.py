import numpy as np
from stl import mesh

def create_dovetail_geometry(center_x, center_y, z_pos, width, height, depth, is_male=True):
    """Create a simple rectangular dovetail mesh (male or female)."""
    # Adjust dimensions for female part (slightly larger for clearance)
    if not is_male:
        width *= 1.05
        height *= 1.05
        depth *= 1.05
        # For female part, we need to recess into the surface
        z_pos -= depth
    
    # Define the 8 vertices of the rectangular peg/hole
    vertices = np.array([
        # Front face (centered at z_pos)
        [center_x - width/2, center_y - height/2, z_pos],
        [center_x + width/2, center_y - height/2, z_pos],
        [center_x + width/2, center_y + height/2, z_pos],
        [center_x - width/2, center_y + height/2, z_pos],
        # Back face (extends depth from z_pos)
        [center_x - width/2, center_y - height/2, z_pos + depth],
        [center_x + width/2, center_y - height/2, z_pos + depth],
        [center_x + width/2, center_y + height/2, z_pos + depth],
        [center_x - width/2, center_y + height/2, z_pos + depth],
    ])
    
    # Define the 12 triangles (2 per face * 6 faces)
    faces = np.array([
        # Front face
        [0,1,2], [0,2,3],
        # Back face
        [4,6,5], [4,7,6],
        # Right face
        [1,5,6], [1,6,2],
        # Left face
        [4,0,3], [4,3,7],
        # Top face
        [3,2,6], [3,6,7],
        # Bottom face
        [0,5,1], [0,4,5]
    ])
    
    return vertices, faces

def find_best_dovetail_position(triangles, z_level, width, height):
    """Find the best position for the dovetail by analyzing the area near the cut plane."""
    # Get points near the cutting plane
    tolerance = (height + width) * 0.1
    near_plane_points = []
    
    for triangle in triangles:
        z_min = min(point[2] for point in triangle)
        z_max = max(point[2] for point in triangle)
        
        if abs(z_level - z_min) < tolerance or abs(z_level - z_max) < tolerance:
            for point in triangle:
                projected_point = [point[0], point[1], z_level]
                near_plane_points.append(projected_point[:2])
    
    if not near_plane_points:
        raise ValueError("No points found near the cutting plane.")
    
    near_plane_points = np.array(near_plane_points)
    
    # Create a grid for density calculation
    x_min, y_min = np.min(near_plane_points, axis=0)
    x_max, y_max = np.max(near_plane_points, axis=0)
    
    grid_resolution = 50
    x_grid = np.linspace(x_min, x_max, grid_resolution)
    y_grid = np.linspace(y_min, y_max, grid_resolution)
    density_map = np.zeros((grid_resolution, grid_resolution))
    
    # Calculate density map with radial sampling
    for i, x in enumerate(x_grid[:-1]):
        for j, y in enumerate(y_grid[:-1]):
            cell_center = np.array([x + (x_grid[i+1] - x)/2, y + (y_grid[j+1] - y)/2])
            
            # Sample in concentric circles around this point
            radii = np.linspace(0, max(width, height) * 2, 10)  # Sample up to 2x dovetail size
            angles = np.linspace(0, 2*np.pi, 16)  # Sample 16 directions
            
            material_found = 0
            total_samples = 0
            
            for radius in radii:
                for angle in angles:
                    sample_point = cell_center + radius * np.array([np.cos(angle), np.sin(angle)])
                    # Check if this point has nearby material
                    distances = np.linalg.norm(near_plane_points - sample_point, axis=1)
                    if np.any(distances < tolerance):
                        material_found += 1 / (radius + 1)  # Weight closer material more heavily
                    total_samples += 1
            
            density_map[i, j] = material_found / total_samples
    
    # Find position with most balanced material distribution
    best_score = -float('inf')
    best_position = None
    
    window_i = max(1, int(grid_resolution * width/(x_max-x_min)))
    window_j = max(1, int(grid_resolution * height/(y_max-y_min)))
    
    for i in range(grid_resolution - window_i):
        for j in range(grid_resolution - window_j):
            region = density_map[i:i+window_i, j:j+window_j]
            
            # Calculate material balance in all directions
            center_i = i + window_i/2
            center_j = j + window_j/2
            
            # Sample in 8 directions from this point
            directions = []
            for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
                sample_i = int(center_i + np.cos(angle) * grid_resolution/4)
                sample_j = int(center_j + np.sin(angle) * grid_resolution/4)
                if 0 <= sample_i < grid_resolution and 0 <= sample_j < grid_resolution:
                    directions.append(density_map[sample_i, sample_j])
            
            # Score based on:
            # 1. Average material density
            # 2. Balance of material (standard deviation of directions)
            # 3. Distance from edges
            avg_density = np.mean(region)
            direction_balance = -np.std(directions)  # Negative because we want minimal variation
            edge_distance = min(center_i, grid_resolution-center_i, center_j, grid_resolution-center_j)
            
            score = avg_density + direction_balance + edge_distance * 0.1
            
            if score > best_score:
                best_score = score
                best_x = x_grid[i] + width/2
                best_y = y_grid[j] + height/2
                best_position = (best_x, best_y)
    
    return best_position

def split_stl_with_dovetail(input_file, output_file1, output_file2):
    # Load the STL file
    main_mesh = mesh.Mesh.from_file(input_file)
    
    # Find the center point to split the mesh
    z_center = (main_mesh.z.max() + main_mesh.z.min()) / 2
    
    # Split the original mesh into two parts
    top_triangles = []
    bottom_triangles = []
    
    for triangle in main_mesh.vectors:
        if np.mean(triangle[:, 2]) > z_center:
            top_triangles.append(triangle)
        else:
            bottom_triangles.append(triangle)
    
    # Calculate centers for each part separately
    top_triangles = np.array(top_triangles)
    bottom_triangles = np.array(bottom_triangles)
    
    # Calculate center for bottom part
    bottom_x_center = (np.max(bottom_triangles[:,:,0]) + np.min(bottom_triangles[:,:,0])) / 2
    bottom_y_center = (np.max(bottom_triangles[:,:,1]) + np.min(bottom_triangles[:,:,1])) / 2
    
    # Calculate center for top part
    top_x_center = (np.max(top_triangles[:,:,0]) + np.min(top_triangles[:,:,0])) / 2
    top_y_center = (np.max(top_triangles[:,:,1]) + np.min(top_triangles[:,:,1])) / 2
    
    # Make dovetail even smaller
    dovetail_width = min(
        (np.max(top_triangles[:,:,0]) - np.min(top_triangles[:,:,0])),
        (np.max(bottom_triangles[:,:,0]) - np.min(bottom_triangles[:,:,0]))
    ) * 0.08  # Reduced to 8% of width
    
    dovetail_height = min(
        (np.max(top_triangles[:,:,1]) - np.min(top_triangles[:,:,1])),
        (np.max(bottom_triangles[:,:,1]) - np.min(bottom_triangles[:,:,1]))
    ) * 0.08  # Reduced to 8% of height
    
    dovetail_depth = (main_mesh.z.max() - main_mesh.z.min()) * 0.1
    
    # Find best position for dovetails
    bottom_x, bottom_y = find_best_dovetail_position(bottom_triangles, z_center, dovetail_width, dovetail_height)
    top_x, top_y = find_best_dovetail_position(top_triangles, z_center, dovetail_width, dovetail_height)
    
    # Create the dovetail geometries with optimal positions
    male_vertices, male_faces = create_dovetail_geometry(
        bottom_x, bottom_y, z_center,
        dovetail_width, dovetail_height, dovetail_depth, True
    )
    
    female_vertices, female_faces = create_dovetail_geometry(
        top_x, top_y, z_center,
        dovetail_width, dovetail_height, dovetail_depth, False
    )
    
    # Create bottom part (with male dovetail)
    bottom_mesh = mesh.Mesh(np.zeros(len(bottom_triangles) + len(male_faces), dtype=mesh.Mesh.dtype))
    for i, triangle in enumerate(bottom_triangles):
        bottom_mesh.vectors[i] = triangle
    for i, face in enumerate(male_faces):
        bottom_mesh.vectors[i + len(bottom_triangles)] = male_vertices[face]
    
    # Create top part (with female dovetail cavity)
    top_mesh = mesh.Mesh(np.zeros(len(top_triangles) + len(female_faces), dtype=mesh.Mesh.dtype))
    for i, triangle in enumerate(top_triangles):
        top_mesh.vectors[i] = triangle
    for i, face in enumerate(female_faces):
        top_mesh.vectors[i + len(top_triangles)] = female_vertices[face]
    
    # Save the resulting meshes
    bottom_mesh.save(output_file1)
    top_mesh.save(output_file2)

if __name__ == "__main__":
    # Example usage
    split_stl_with_dovetail(
        r"E:\iCloud Files\iCloudDrive\3D Printer\Things\Monkey_Butler_Ring_Holder_3703834\files\MonkeyButler.stl",
        "output_part1.stl",
        "output_part2.stl"
    )
