import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
import os
import sys

def generate_report():
    # 1. Find the log files
    log_files = glob.glob('*_log.csv')
    if not log_files:
        print("No log files (*_log.csv) found in the current directory.")
        return

    # Sort files to get the latest ones or process all
    log_files.sort()
    
    print(f"Found log files: {log_files}")
    
    # 2. Load and Combine Data
    all_dfs = []
    for f in log_files:
        try:
            # Try reading with default UTF-8
            df = pd.read_csv(f)
            # Basic validation of required columns for new format
            if 'NonPagedPoolMB' in df.columns:
                all_dfs.append(df)
            else:
                print(f"Skipping {f}: Old format (missing NonPagedPoolMB)")
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    if not all_dfs:
        print("Could not read any valid data (New Format).")
        return

    df_main = pd.concat(all_dfs, ignore_index=True)
    
    # Clean and convert Timestamp
    df_main['Timestamp'] = pd.to_datetime(df_main['Timestamp'])
    df_main = df_main.sort_values('Timestamp')

    # 3. Process Data for Visualization
    
    # Helper to extract top lists (Memory or Handles)
    def extract_top_data(prefix_name, prefix_val, count, val_col_name):
        data = []
        for index, row in df_main.iterrows():
            ts = row['Timestamp']
            for i in range(1, count + 1):
                name_col = f'{prefix_name}{i}_Name'
                val_col = f'{prefix_val}{i}_{val_col_name}' # e.g. TopMem1_MB or TopHandle1_Count
                
                if name_col in row and val_col in row:
                    p_name = row[name_col]
                    p_val = row[val_col]
                    
                    if pd.notna(p_name) and pd.notna(p_val):
                        data.append({
                            'Timestamp': ts,
                            'ProcessName': str(p_name),
                            'Value': float(p_val)
                        })
        return pd.DataFrame(data)

    # Extract Memory Data
    df_mem_raw = extract_top_data('TopMem', 'TopMem', 10, 'MB')
    # Aggregate by ProcessName
    df_mem = df_mem_raw.groupby(['Timestamp', 'ProcessName'], as_index=False)['Value'].sum()
    
    # Extract Handle Data (No conversion needed for Count)
    df_handle_raw = extract_top_data('TopHandle', 'TopHandle', 5, 'Count')
    df_handle = df_handle_raw.groupby(['Timestamp', 'ProcessName'], as_index=False)['Value'].sum()

    # Filter Logic
    def filter_top_consumers(df, value_col, top_n=10):
        if df.empty: return df
        # Find top consumers based on MAX usage over the period
        max_usage = df.groupby('ProcessName')[value_col].max().sort_values(ascending=False)
        top_consumers = max_usage.head(top_n).index.tolist()
        return df[df['ProcessName'].isin(top_consumers)], top_consumers

    # Reduced density: Top 5 for Memory, Top 3 for Handles
    df_mem_filtered, mem_consumers = filter_top_consumers(df_mem, 'Value', 5)
    df_handle_filtered, handle_consumers = filter_top_consumers(df_handle, 'Value', 3)

    # 4. Create Interactive Plot
    
    # 4 Subplots
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "1. 總系統記憶體使用量 (實體記憶體) - 當紅色區域接近灰色虛線時，代表記憶體快被吃光了 / Total System Memory Usage",
            "2. 核心集區使用量 (驅動程式洩漏偵測) - <b>橘色線</b>若持續上升不降，代表驅動程式有問題 / Kernel Pool Usage (Driver Leak)",
            "3. 前 5 大應用程式記憶體佔用 (應用程式洩漏偵測) - 這裡抓出誰是吃記憶體怪獸 / Top 5 Process Memory Usage",
            "4. 前 3 大應用程式控制代碼佔用 (資源洩漏偵測) - <b>lsm.exe</b> 或資安軟體若出現在這且持續上升，通常是元兇 / Top 3 Process Handle Count"
        )
    )

    # Plot 1: Total & Used Memory (MB)
    fig.add_trace(go.Scatter(x=df_main['Timestamp'], y=df_main['TotalMB'], name="總記憶體 (Total MB)", line=dict(color='gray', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_main['Timestamp'], y=df_main['UsedMB'], name="已用記憶體 (Used MB)", line=dict(color='red'), fill='tozeroy'), row=1, col=1)
    
    # Plot 2: Kernel Pools (MB)
    fig.add_trace(go.Scatter(x=df_main['Timestamp'], y=df_main['NonPagedPoolMB'], name="非分頁集區 (Non-Paged Pool) [關鍵]", line=dict(color='orange', width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_main['Timestamp'], y=df_main['PagedPoolMB'], name="分頁集區 (Paged Pool)", line=dict(color='cyan')), row=2, col=1)

    # Plot 3: Top Process Memory (MB)
    if not df_mem_filtered.empty:
        for proc_name in mem_consumers:
            proc_df = df_mem_filtered[df_mem_filtered['ProcessName'] == proc_name]
            fig.add_trace(go.Scatter(
                x=proc_df['Timestamp'], y=proc_df['Value'], name=f"Mem: {proc_name}",
                mode='lines', hoverinfo='x+y+name'
            ), row=3, col=1)

    # Plot 4: Top Process Handles (Count)
    if not df_handle_filtered.empty:
        for proc_name in handle_consumers:
            proc_df = df_handle_filtered[df_handle_filtered['ProcessName'] == proc_name]
            fig.add_trace(go.Scatter(
                x=proc_df['Timestamp'], y=proc_df['Value'], name=f"Handles: {proc_name}",
                 mode='lines', hoverinfo='x+y+name' 
            ), row=4, col=1)

    # Layout Updates
    fig.update_layout(
        title_text="系統資源鑑識報告 / System Resource Forensics Report",
        height=1200, 
        hovermode="x unified",
        hoverlabel=dict(
            namelength=-1,
        ),
        template="plotly_dark",
        margin=dict(t=100)
    )
    
    fig.update_yaxes(title_text="MB", row=1, col=1, dtick=5000, tickformat="d") # 5000MB intervals, integer format
    fig.update_yaxes(title_text="MB", row=2, col=1, dtick=20, tickformat=".1f") # 20MB intervals, 1 decimal place
    fig.update_yaxes(title_text="MB", row=3, col=1, dtick=250, tickformat="d")  # 250MB intervals, integer format
    fig.update_yaxes(title_text="數量 (Count)", row=4, col=1, dtick=1000, tickformat="d") # 1000 count intervals, integer format

    # 5. Save to HTML
    output_file = 'MemoryForensicsReport.html'
    fig.write_html(output_file)
    print(f"Successfully created report: {os.path.abspath(output_file)}")
    # Add Chinese success message here
    print("\n報告已成功生成！請打開 MemoryForensicsReport.html 查看。")
    print("Report has been successfully generated! Please open MemoryForensicsReport.html to view.")

if __name__ == "__main__":
    generate_report()