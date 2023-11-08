import xarray
import pandas as pd
import matplotlib.pyplot as plt
import ctd_tools.ctd_parameters as ctdparams
import numpy as np
import gsw

class CtdPlotter:
    """ Plots different diagrams for CTD data from a xarray Dataset. """

    def __init__(self, data: xarray.Dataset):
        self.data = data            

    def __plot_density_isolines(self, plt):
        """ Plots density isolines into a given T-S diagram plot """

        ds = self.data 

        # Define the min / max values for plotting isopycnals
        t_min = ds[ctdparams.TEMPERATURE].values.min()
        t_max = ds[ctdparams.TEMPERATURE].values.max()
        s_min = ds[ctdparams.SALINITY].values.min()
        s_max = ds[ctdparams.SALINITY].values.max()

        # Calculate "padding" for temperature axis
        t_width = t_max - t_min
        t_min -= (t_width * 0.1)
        t_max += (t_width * 0.1)
        
        # Calcualte "padding" for salinity axis
        s_width = s_max - s_min
        s_min -= (s_width * 0.1)
        s_max += (s_width * 0.1)

        # Calculate how many gridcells we need in the x and y dimensions
        factor = round(max([t_width,s_width]) / min([t_width, s_width]))
        if s_width > t_width:
            xdim = 150   # round(round(s_max - s_min, 3) / 0.001)
            ydim = round(150 / factor)   # round(round(t_max - t_min, 3) / 0.001)
        else:
            ydim = 150
            xdim = round(150 / factor)

        density = np.zeros((int(ydim), int(xdim)))

        # Create temp and salt vectors of appropiate dimensions
        ti = np.linspace(t_min,t_max,ydim)
        si = np.linspace(s_min,s_max,xdim)

        # Loop to fill in grid with densities
        for j in range(0,int(ydim)):
            for i in range(0, int(xdim)):
                density[j,i] = gsw.rho(si[i], ti[j],0)

        # Subtract 1000 to convert density to sigma-t
        sigma_t = density - 1000

        # Plot isolines
        CS = plt.contour(si, ti, sigma_t, linewidths=1, linestyles='dashed', colors='gray')
        plt.clabel(CS, fontsize=8, inline=1, fmt='%1.2f') # Label every second level

        # Add sigma_0 in gray in the left upper corner
        plt.text(0.02, 0.95, r"$\sigma_0$", color='gray', fontsize=18, 
                fontweight='bold', transform=plt.gca().transAxes)
        

    def plot_ts_diagram(self, output_file=None, title='T-S Diagram', dot_size=70, use_colormap=True, 
                        show_density_isolines=True, colormap='jet', show_lines_between_dots=True):
        ''' Plots a T-S diagram. '''

        # Check for necessary data keys
        if ctdparams.TEMPERATURE not in self.data:
            raise ValueError('Temperature data is missing. This is necessary for plotting a T-S diagram.')
        if ctdparams.SALINITY not in self.data:
            raise ValueError('Salinity data is missing. This is necessary for plotting a T-S diagram.')
        if ctdparams.DEPTH not in self.data:
            raise ValueError('Depth data is missing. This is necessary for plotting a T-S diagram.')
        
        temperature = self.data[ctdparams.TEMPERATURE]
        salinity = self.data[ctdparams.SALINITY]
        depth = self.data[ctdparams.DEPTH]

        # Create figure
        fig = plt.figure(figsize=(15, 8))

        # Create a line plot of temperature vs. salinity
        if show_lines_between_dots:
            plt.plot(salinity, temperature, color='gray', linestyle='-', linewidth=0.5)

        # Create a scatter plot of temperature vs. salinity
        if use_colormap:
            plt.scatter(salinity, temperature, c=depth, cmap=colormap, marker='o', s=dot_size)
            plt.colorbar(label='Depth [m]') # Plot legend for colormap
        else:
            plt.scatter(salinity, temperature, c='black', marker='o', s=dot_size)

        # Set plot labels and title
        plt.xlabel('Salinity [PSU]')
        plt.ylabel(self.data[ctdparams.TEMPERATURE].attrs['long_name']+ \
                   " ["+self.data[ctdparams.TEMPERATURE].attrs['units']+"]")

        # Set plot title
        plt.title(title)

        # Integrate density isolines if wanted
        if show_density_isolines:
            self.__plot_density_isolines(plt)

        # Enable tight layout
        plt.tight_layout()

        # Show the plot
        if not output_file:
            plt.show()

        # Save the plot as an image
        elif output_file:
            plt.savefig(output_file)

    def plot_profile(self, output_file=None):
        ''' Plots a vertical CTD profile for temperature and salinity. '''

        # Check for necessary data keys
        if ctdparams.TEMPERATURE not in self.data:
            raise ValueError('Temperature data is missing. This is necessary for plotting a T-S diagram.')
        if ctdparams.SALINITY not in self.data:
            raise ValueError('Salinity data is missing. This is necessary for plotting a T-S diagram.')
        if ctdparams.DEPTH not in self.data:
            raise ValueError('Depth data is missing. This is necessary for plotting a T-S diagram.')
        
        # Extract temperature, salinity, and depth variables from the dataset
        temperature = self.data[ctdparams.TEMPERATURE]
        salinity = self.data[ctdparams.SALINITY]
        depth = self.data[ctdparams.DEPTH]

        # Create a scatter plot of salinity and temperature with depth as the y-axis
        fig, ax1 = plt.subplots(figsize=(8, 6))

        # Plot salinity on the primary y-axis
        color = 'blue'
        salinity_min = salinity.min()
        salinity_max = salinity.max()
        salinity_padding = ((salinity_max - salinity_min) * 0.1)
        salinity_range = ((salinity_min - salinity_padding), (salinity_max + salinity_padding))        
        ax1.set_xlim(salinity_range)
        ax1.set_xlabel('Salinity', color=color)
        ax1.set_ylabel('Depth')
        ax1.scatter(salinity, depth, c=color, label='Salinity', s=3)
        ax1.tick_params(axis='x', labelcolor=color)

        # Create a twin axis for temperature
        ax2 = ax1.twiny()

        # Plot temperature on the secondary x-axis
        color = 'red'
        temperature_min = temperature.min()
        temperature_max = temperature.max()
        temperature_padding = ((temperature_max - temperature_min) * 0.1)
        temperature_range = ((temperature_min - temperature_padding), (temperature_max + temperature_padding))
        ax2.set_xlim(temperature_range)
        ax2.set_xlabel('Temperature', color=color)
        ax2.scatter(temperature, depth, c=color, label='Temperature', s=3)
        ax2.tick_params(axis='x', labelcolor=color)

        # Plot lines between the dots
        ax1.plot(salinity, depth, color='blue', linestyle='-', linewidth=0.5)
        ax2.plot(temperature, depth, color='red', linestyle='-', linewidth=0.5)

        # Set axis labels and title
        ax1.set_title('Salinity and Temperature Profiles')

        # Add a legend
        ax1.legend()

        # Add grid lines
        ax1.grid(color='gray', linestyle='--', linewidth=0.5)

        # Adjust layout
        fig.tight_layout()

        # Show the plot
        if not output_file:
            plt.show()

        # Save the plot as an image
        elif output_file:
            plt.savefig(output_file)

    def plot_time_series(self, parameter_name, output_file=None):
        ''' Plots a times series for a given parameter. '''

        # Create a plot
        fig, ax = plt.subplots(figsize=(10, 5))  # Customize figure size

        # Plot the 'temperature' data variable
        self.data[parameter_name].plot.line('b-', ax=ax)

        # Creating string date range
        first_date = np.min(self.data[ctdparams.TIME].values).astype('datetime64[D]')
        last_date = np.max(self.data[ctdparams.TIME].values).astype('datetime64[D]')
        if first_date == last_date:
            dateline = f"on {first_date}"
        else:
            dateline = f"{first_date} to {last_date}"

        # Customize the plot with titles and labels
        ax.set_title(f"{self.data[parameter_name].attrs['long_name']} over time ({dateline})")
        ax.set_xlabel('Time')
        ax.set_ylabel(self.data[parameter_name].attrs['long_name']+" ["+self.data[parameter_name].attrs['units']+"]")

        # Optionally, you can format the x-axis to better display dates
        plt.gcf().autofmt_xdate()  # Auto-format date on x-axis

        # Show the plot
        if not output_file:
            plt.show()

        # Save the plot as an image
        elif output_file:
            plt.savefig(output_file)
