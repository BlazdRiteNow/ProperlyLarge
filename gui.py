import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
from tkinter import messagebox
import sys
import os
from main import process_stl
from io import StringIO

class OutputRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.text_widget.configure(state='normal')

    def write(self, str):
        self.text_widget.configure(state='normal')
        self.text_widget.insert('end', str)
        self.text_widget.see('end')
        self.text_widget.configure(state='disabled')
        self.text_widget.update()

    def flush(self):
        pass

class BigStuffGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Make It Big - STL Scaler")
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Default config - moved here to ensure it's created before use
        self.config = {
            'target_height_feet': 2,
            'printer_bed_size': 300,
            'safety_margin': 5,
            'input_file': None,
            'height_axis': 'z',
            'output_base_dir': r"F:\Homebrew\Big Stuff"
        }
        
        # File selection
        ttk.Label(main_frame, text="Input STL:").grid(row=0, column=0, sticky=tk.W)
        self.file_label = ttk.Label(main_frame, text="No file selected", width=50)
        self.file_label.grid(row=0, column=1, sticky=tk.W)
        ttk.Button(main_frame, text="Browse", command=self.browse_file).grid(row=0, column=2)
        
        # Height input
        ttk.Label(main_frame, text="Target Height (feet):").grid(row=1, column=0, sticky=tk.W)
        self.height_var = tk.StringVar(value="2")
        ttk.Entry(main_frame, textvariable=self.height_var, width=10).grid(row=1, column=1, sticky=tk.W)
        
        # Printer bed size
        ttk.Label(main_frame, text="Printer Bed Size (mm):").grid(row=2, column=0, sticky=tk.W)
        self.bed_size_var = tk.StringVar(value="300")
        ttk.Entry(main_frame, textvariable=self.bed_size_var, width=10).grid(row=2, column=1, sticky=tk.W)
        
        # Safety margin
        ttk.Label(main_frame, text="Safety Margin (mm):").grid(row=3, column=0, sticky=tk.W)
        self.margin_var = tk.StringVar(value="5")
        ttk.Entry(main_frame, textvariable=self.margin_var, width=10).grid(row=3, column=1, sticky=tk.W)
        
        # Height axis selection
        ttk.Label(main_frame, text="Height Axis:").grid(row=4, column=0, sticky=tk.W)
        self.axis_var = tk.StringVar(value="z")
        axis_frame = ttk.Frame(main_frame)
        axis_frame.grid(row=4, column=1, sticky=tk.W)
        ttk.Radiobutton(axis_frame, text="X", variable=self.axis_var, value="x").grid(row=0, column=0)
        ttk.Radiobutton(axis_frame, text="Y", variable=self.axis_var, value="y").grid(row=0, column=1)
        ttk.Radiobutton(axis_frame, text="Z", variable=self.axis_var, value="z").grid(row=0, column=2)
        
        # Process button
        ttk.Button(main_frame, text="Process STL", command=self.process_file).grid(row=5, column=0, columnspan=3, pady=20)
        
        # Output text area
        self.output_text = scrolledtext.ScrolledText(main_frame, height=20, width=80)
        self.output_text.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.output_text.configure(state='disabled')
        
        # Add padding to all children
        for child in main_frame.winfo_children():
            child.grid_configure(padx=5, pady=5)
            
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select STL file",
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")]
        )
        if filename:
            self.config['input_file'] = filename
            self.file_label.config(text=os.path.basename(filename))
            
    def process_file(self):
        if not self.config['input_file']:
            messagebox.showerror("Error", "Please select an input file first")
            return
            
        try:
            # Clear output text
            self.output_text.configure(state='normal')
            self.output_text.delete(1.0, tk.END)
            self.output_text.configure(state='disabled')
            
            # Update config from GUI values
            self.config.update({
                'target_height_feet': float(self.height_var.get()),
                'printer_bed_size': float(self.bed_size_var.get()),
                'safety_margin': float(self.margin_var.get()),
                'height_axis': self.axis_var.get()
            })
            
            # Redirect stdout to our text widget
            old_stdout = sys.stdout
            sys.stdout = OutputRedirector(self.output_text)
            
            # Run the processing with our config
            process_stl(self.config)
            
            # Restore stdout
            sys.stdout = old_stdout
            
            messagebox.showinfo("Success", "STL processing complete!")
            
        except Exception as e:
            sys.stdout = old_stdout
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = BigStuffGUI(root)
    root.mainloop() 