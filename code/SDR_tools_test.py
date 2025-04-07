import tkinter as tk
from tkinter import ttk
import json

class TestPoliceUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Police Scanner UI Test")
        self.root.geometry("800x600")
        
        self.police_frequencies = {}
        self.load_police_frequencies()
        
        # Main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create location selection UI
        location_frame = ttk.LabelFrame(main_frame, text="Location Selection")
        location_frame.pack(fill=tk.X, pady=5)
        
        # Country selection
        country_frame = ttk.Frame(location_frame)
        country_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(country_frame, text="Country:").pack(side=tk.LEFT, padx=5)
        self.country_var = tk.StringVar(value="United States")
        self.country_combo = ttk.Combobox(country_frame, textvariable=self.country_var, state="readonly")
        self.country_combo['values'] = list(self.police_frequencies.keys())
        self.country_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.country_combo.bind("<<ComboboxSelected>>", self.update_states)
        
        # State/Region selection
        state_frame = ttk.Frame(location_frame)
        state_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(state_frame, text="State:").pack(side=tk.LEFT, padx=5)
        self.state_var = tk.StringVar()
        self.state_combo = ttk.Combobox(state_frame, textvariable=self.state_var, state="readonly")
        self.state_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.state_combo.bind("<<ComboboxSelected>>", self.update_cities)
        
        # City selection
        city_frame = ttk.Frame(location_frame)
        city_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(city_frame, text="City:").pack(side=tk.LEFT, padx=5)
        self.city_var = tk.StringVar()
        self.city_combo = ttk.Combobox(city_frame, textvariable=self.city_var, state="readonly")
        self.city_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.city_combo.bind("<<ComboboxSelected>>", self.update_services)
        
        # Service selection
        service_frame = ttk.Frame(location_frame)
        service_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(service_frame, text="Service:").pack(side=tk.LEFT, padx=5)
        self.service_var = tk.StringVar()
        self.service_combo = ttk.Combobox(service_frame, textvariable=self.service_var, state="readonly")
        self.service_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.service_combo.bind("<<ComboboxSelected>>", self.update_frequencies)
        
        # Frequency table
        freq_frame = ttk.LabelFrame(main_frame, text="Frequencies")
        freq_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ('Frequency (MHz)', 'Description')
        self.freq_tree = ttk.Treeview(freq_frame, columns=columns, show='headings')
        for col in columns:
            self.freq_tree.heading(col, text=col)
            self.freq_tree.column(col, width=150)
        self.freq_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Initialize the UI
        self.update_states()
    
    def load_police_frequencies(self):
        """Load police frequencies from JSON file"""
        try:
            with open("police_frequencies.json", "r") as f:
                self.police_frequencies = json.load(f)
                print(f"Loaded police frequencies: {len(self.police_frequencies)} countries")
        except Exception as e:
            print(f"Error loading police frequencies: {e}")
            # Create minimal example data
            self.police_frequencies = {
                "United States": {
                    "Example State": {
                        "Example City": {
                            "Police": [
                                "460.500 MHz - Example Police Dispatch"
                            ]
                        }
                    }
                }
            }
    
    def update_states(self, event=None):
        """Update states/regions based on selected country"""
        country = self.country_var.get()
        
        if country in self.police_frequencies:
            # Get states/regions for the selected country
            states = list(self.police_frequencies[country].keys())
            self.state_combo['values'] = states
            
            if states:
                self.state_combo.current(0)
                self.update_cities()
                self.status_label.config(text=f"Found {len(states)} states for {country}")
            else:
                self.state_combo.set('')
                self.status_label.config(text=f"No states found for {country}")
        else:
            self.state_combo['values'] = []
            self.state_combo.set('')
            self.status_label.config(text=f"No states found for {country}")
            
        # Clear dependent dropdowns
        self.city_combo['values'] = []
        self.city_combo.set('')
        self.service_combo['values'] = []
        self.service_combo.set('')
        self.clear_frequency_display()
    
    def update_cities(self, event=None):
        """Update cities based on selected state/region"""
        country = self.country_var.get()
        state = self.state_var.get()
        
        if country in self.police_frequencies and state in self.police_frequencies[country]:
            # Get cities for the selected state
            cities = list(self.police_frequencies[country][state].keys())
            self.city_combo['values'] = cities
            
            if cities:
                self.city_combo.current(0)
                self.update_services()
                self.status_label.config(text=f"Found {len(cities)} cities in {state}")
            else:
                self.city_combo.set('')
                self.status_label.config(text=f"No cities found for {state}")
        else:
            self.city_combo['values'] = []
            self.city_combo.set('')
            self.status_label.config(text=f"No cities found for {state}")
            
        # Clear dependent dropdowns
        self.service_combo['values'] = []
        self.service_combo.set('')
        self.clear_frequency_display()
    
    def update_services(self, event=None):
        """Update services based on selected city"""
        country = self.country_var.get()
        state = self.state_var.get()
        city = self.city_var.get()
        
        if (country in self.police_frequencies and 
            state in self.police_frequencies[country] and 
            city in self.police_frequencies[country][state]):
            
            # Get services for the selected city
            services = list(self.police_frequencies[country][state][city].keys())
            self.service_combo['values'] = services
            
            if services:
                self.service_combo.current(0)
                self.update_frequencies()
                self.status_label.config(text=f"Found {len(services)} services for {city}")
            else:
                self.service_combo.set('')
                self.status_label.config(text=f"No services found for {city}")
        else:
            self.service_combo['values'] = []
            self.service_combo.set('')
            self.status_label.config(text=f"No services found for {city}")
        
        self.clear_frequency_display()
    
    def update_frequencies(self, event=None):
        """Update frequencies based on selected service"""
        country = self.country_var.get()
        state = self.state_var.get()
        city = self.city_var.get()
        service = self.service_var.get()
        
        # Clear existing items
        self.clear_frequency_display()
        
        if not all([country, state, city, service]):
            return
            
        try:
            # Access the frequencies list for this service
            frequencies_list = self.police_frequencies[country][state][city][service]
            
            # Process frequencies
            for freq_entry in frequencies_list:
                parts = freq_entry.split(' - ', 1)
                freq_str = parts[0].strip()
                desc = parts[1] if len(parts) > 1 else service
                
                # Remove MHz at the end if present for the frequency tree
                if freq_str.endswith(" MHz"):
                    freq_value = freq_str[:-4]
                else:
                    freq_value = freq_str
                
                # Add to treeview
                self.freq_tree.insert('', 'end', values=(freq_value, desc))
                
            self.status_label.config(text=f"Found {len(frequencies_list)} frequencies for {service} in {city}")
            
        except (KeyError, Exception) as e:
            self.status_label.config(text=f"Error loading frequencies: {e}")
    
    def clear_frequency_display(self):
        """Clear the frequency displays"""
        for item in self.freq_tree.get_children():
            self.freq_tree.delete(item)

if __name__ == "__main__":
    root = tk.Tk()
    app = TestPoliceUI(root)
    root.mainloop() 