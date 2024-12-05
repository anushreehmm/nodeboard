#!/usr/bin/env python
# coding: utf-8

# Import necessary modules
import os  # For file and directory operations
import configparser  # For reading configuration files
import pandas as pd  # For data manipulation and analysis
import dash  # For building web applications
from dash import dcc, html  # Dash core components and HTML elements
from dash.dependencies import Input, Output, State  # For callbacks and interactions
import dash_table  # For creating interactive data tables
import dash_bootstrap_components as dbc  # For using Bootstrap components in Dash
import re  # For regular expression matching
import threading  # For running the app in a separate thread

# Read configuration file to get application settings
config = configparser.ConfigParser()
config.read('config.ini')  # Load configuration file

# Extract the downloads path and file patterns from the configuration
downloads_path = config.get('Paths', 'downloads_path').strip('"')
file1_pattern = config.get('Patterns', 'file1_pattern').strip('"')
file2_pattern = config.get('Patterns', 'file2_pattern').strip('"')

# Check if the specified downloads path exists
if not os.path.exists(downloads_path):
    raise FileNotFoundError(f"The specified downloads path does not exist: {downloads_path}")

# Function to find the latest file matching a specific pattern in the downloads path
def get_latest_file(pattern):
    # List all files in the downloads path
    files = os.listdir(downloads_path)
    # Filter files that match the given pattern
    matched_files = [f for f in files if re.match(pattern, f)]
    if matched_files:
        # Find the most recently created file
        latest_file = max(matched_files, key=lambda f: os.path.getctime(os.path.join(downloads_path, f)))
        return os.path.join(downloads_path, latest_file)
    raise FileNotFoundError("No files matching the pattern were found.")

# Attempt to get the latest files matching the patterns
try:
    file1_path = get_latest_file(file1_pattern)
    file2_path = get_latest_file(file2_pattern)
except FileNotFoundError as e:
    print(e)

# Function to clean and preprocess the first dataset
def data1_clean(file1_path):
    df = pd.read_excel(file1_path, skiprows=5)  # Load Excel file and skip header rows
    df = df.rename(columns={  # Rename relevant columns
        'Unnamed: 0': 'Sl.no',
        'Unnamed: 1': 'IP Address',
        'Unnamed: 4': 'Event',
        'Unnamed: 6': 'Alarm Time',
        'Unnamed: 2': 'Node Alias'  
    })
    # Drop unnecessary columns
    df = df.drop(columns=['Sl.no', 'Clear Time', 'Duration', 'Description', 'Host Name'], errors='ignore')
    df = df.dropna(subset=['Node Alias', 'Alarm Time'])  # Drop rows with missing essential data
    df['Alarm Time'] = pd.to_datetime(df['Alarm Time'], errors='coerce')  # Convert alarm time to datetime
    df = df.dropna(subset=['Alarm Time'])  # Remove invalid datetime rows
    return df

# Function to clean and preprocess the second dataset
def data2_clean(file2_path):
    df = pd.read_excel(file2_path)  # Load Excel file
    df = df.drop([0, 1, 2, 3, 4], axis=0).reset_index(drop=True)  # Remove unwanted header rows
    # Drop unnecessary columns
    df = df.drop(columns=['Unnamed: 2', 'Unnamed: 3'], errors='ignore')
    # Rename columns for clarity
    df = df.rename(columns={
        'Unnamed: 0': 'Node Alias',
        'Unnamed: 1': 'IP Address',
        'Unnamed: 4': 'Availability',
        'Unnamed: 5': 'Latency(msec)',
        'Unnamed: 6': 'Packet Loss(%)'
    })
    # Convert relevant columns to numeric and handle errors
    df['Packet Loss(%)'] = pd.to_numeric(df['Packet Loss(%)'], errors='coerce')
    df['Availability'] = pd.to_numeric(df['Availability'], errors='coerce')
    df['Latency(msec)'] = pd.to_numeric(df['Latency(msec)'], errors='coerce')
    df = df.dropna(subset=['Packet Loss(%)', 'Availability', 'Latency(msec)'])  # Drop rows with missing data
    return df

# Clean and preprocess the datasets
df1_cleaned = data1_clean(file1_path)
df2_cleaned = data2_clean(file2_path)

# Merge the cleaned datasets on the 'IP Address' column
merged_df = pd.merge(df1_cleaned, df2_cleaned[['IP Address', 'Availability']], on='IP Address', how='left')

# Calculate downtime count per node
downtime_count = (
    merged_df.groupby('Node Alias')['Alarm Time']
    .nunique()
    .reset_index(name='Downtime Count')
)

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

# Define date range boundaries for the date picker
min_date = merged_df['Alarm Time'].min()
max_date = merged_df['Alarm Time'].max()

# Handle cases where dates are missing
if pd.isnull(min_date):
    min_date = pd.to_datetime('2020-01-01')  # Default start date
if pd.isnull(max_date):
    max_date = pd.to_datetime('2020-12-31')  # Default end date

# Define custom styles for UI elements
custom_label_style = {
    "color": "#000000",  # Black text
    "fontWeight": "bold",
    "marginBottom": "5px"
}

custom_dropdown_style = {
    "backgroundColor": "#ffffff",  # Light background
    "color": "#000000",  # Dark text
    "border": "1px solid #007bff",  # Blue border
    "borderRadius": "5px",  # Rounded corners
    "padding": "8px 12px",  # Padding for spacing
    "fontSize": "14px",  # Adjusted font size
    "boxShadow": "0 4px 8px rgba(0, 0, 0, 0.1)"  # Slight shadow effect
}

# Create downtime count options for the dropdown
downtime_options = [{'label': str(count), 'value': count} for count in downtime_count['Downtime Count'].unique()]

# Define the app layout
app.layout = dbc.Container(
    fluid=True,
    style={
        "backgroundColor": "#f5f5f5",  # Light background
        "minHeight": "100vh",  # Full height
        "padding": "20px"  # Padding for spacing
    },
    children=[
        # Header section
        dbc.Row(
            dbc.Col(
                html.H1(
                    "Node Availability Report",
                    className="text-center text-light bg-primary p-4 mb-4 rounded",
                    style={"fontSize": "36px", "font-family": "Roboto, sans-serif"}
                ),
                width=12
            )
        ),
        # Filter section
        dbc.Row(
            [
                # Date range picker
                dbc.Col(
                    [
                        html.Label("Select Date Range:", style=custom_label_style),
                        dcc.DatePickerRange(
                            id='date-range',
                            start_date=None,  # No predefined start date
                            end_date=None,    # No predefined end date
                            min_date_allowed=min_date.date(),  # Specify minimum date
                            max_date_allowed=max_date.date(),  # Specify maximum date
                            display_format='YYYY-MM-DD',
                            style=custom_dropdown_style
                        )
                    ],
                    width=4
                ),
                # Downtime count dropdown
                dbc.Col(
                    [
                        html.Label("Select Downtime Count:", style=custom_label_style),
                        dcc.Dropdown(
                            id='downtime-dropdown',
                            options=[
                                {'label': '1-3', 'value': '1-3'},
                                {'label': '4-5', 'value': '4-5'},
                                {'label': '>5', 'value': '>5'},
                                {'label': '>10', 'value': '>10'}  # Additional filter
                            ],
                            value='1-3',  # Default selection
                            placeholder='Select downtime count criteria',
                            style=custom_dropdown_style
                        )
                    ],
                    width=4
                ),
                # Apply filters button
                dbc.Col(
                    [
                        html.Br(),
                        dbc.Button(
                            "Apply Filters",
                            id='filter-button',
                            color="success"
                        )
                    ],
                    width=4
                )
            ],
            className="mb-4"
        ),
        # Data table section
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H4("Filtered Node Availability")),
                        dbc.CardBody(
                            dash_table.DataTable(
                                id='filtered-table',
                                columns=[{"name": col, "id": col} for col in downtime_count.columns],
                                data=downtime_count.to_dict('records'),  # Set initial table data
                                page_size=10,
                                style_table={
                                    'overflowX': 'auto',
                                    'border': '1px solid #ddd',
                                    'borderRadius': '8px',
                                    'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)'  # Shadow effect
                                },
                                style_header={
                                    'backgroundColor': '#4CAF50',  # Green header background
                                    'color': 'white',  # White text
                                    'fontWeight': 'bold',
                                    'textAlign': 'center'
                                },
                                style_cell={
                                    'padding': '8px',
                                    'textAlign': 'center',
                                    'border': '1px solid #ddd'
                                }
                            )
                        )
                    ]
                ),
                width=12
            )
        )
    ]
)

# Define the callback to filter data based on selected date range and downtime count
@app.callback(
    Output('filtered-table', 'data'),
    Input('filter-button', 'n_clicks'),
    State('date-range', 'start_date'),
    State('date-range', 'end_date'),
    State('downtime-dropdown', 'value')
)
def filter_data(n_clicks, start_date, end_date, downtime_value):
    if n_clicks is None:
        return downtime_count.to_dict('records')  # Default display
    # Filter data based on downtime count
    filtered_df = downtime_count
    if downtime_value == '1-3':
        filtered_df = filtered_df[filtered_df['Downtime Count'] <= 3]
    elif downtime_value == '4-5':
        filtered_df = filtered_df[(filtered_df['Downtime Count'] > 3) & (filtered_df['Downtime Count'] <= 5)]
    elif downtime_value == '>5':
        filtered_df = filtered_df[filtered_df['Downtime Count'] > 5]
    elif downtime_value == '>10':
        filtered_df = filtered_df[filtered_df['Downtime Count'] > 10]

    # If start and end dates are provided, filter based on alarm time
    if start_date and end_date:
        filtered_df = filtered_df[
            (filtered_df['Alarm Time'] >= pd.to_datetime(start_date)) & 
            (filtered_df['Alarm Time'] <= pd.to_datetime(end_date))
        ]
    return filtered_df.to_dict('records')

# Run the app in a separate thread for easy execution in a local environment
if __name__ == '__main__':
    threading.Thread(target=app.run_server, kwargs={"debug": True, "use_reloader": False}).start()
