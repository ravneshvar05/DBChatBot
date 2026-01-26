"""
Visualization Service using Plotly.

Automatically generates interactive charts based on data structure.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any, Optional

class Visualizer:
    """Generates Plotly charts from data."""
    
    @staticmethod
    def create_chart(data: List[Dict[str, Any]]) -> Optional[go.Figure]:
        """
        Analyze data and create the most appropriate chart.
        Returns None if no suitable chart can be created.
        """
        if not data or len(data) < 2:
            return None
            
        try:
            df = pd.DataFrame(data)
            
            # CLEANING: Try to convert object columns to numeric if possible
            for col in df.columns:
                # Skip explicit text columns like names
                if "name" in col.lower() or "description" in col.lower():
                    continue
                try:
                    df[col] = pd.to_numeric(df[col])
                except:
                    pass
            
            # Identify columns
            # Exclude IDs from being treated as meaningful numerics
            numeric_cols = [
                c for c in df.select_dtypes(include=['number']).columns 
                if 'id' not in c.lower()
            ]
            
            categorical_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
            
            # Fallback: If no categorical, treat 'id' or first column as label
            if not categorical_cols and len(df.columns) > 0:
                categorical_cols = [df.columns[0]]

            # Case 1: Time Series (Line Chart)
            time_cols = [c for c in df.columns if 'date' in c.lower() or 'year' in c.lower()]
            if time_cols and numeric_cols:
                time = time_cols[0]
                num = numeric_cols[0]
                df = df.sort_values(by=time)
                return px.line(
                    df, x=time, y=num,
                    title=f"{num.title()} Over Time",
                    template="plotly_dark",
                    markers=True
                )

            # Case 2: Bar Chart (1 Cat + >=1 Num)
            # Relaxed: Only need at least one numeric.
            if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                cat = categorical_cols[0]
                num = numeric_cols[0]
                
                # Limit to top 20 for readability
                df_sorted = df.sort_values(by=num, ascending=False).head(20)
                
                return px.bar(
                    df_sorted, x=cat, y=num,
                    title=f"{num.replace('_', ' ').title()} by {cat.replace('_', ' ').title()}",
                    template="plotly_dark",
                    color=num,
                    color_continuous_scale="Viridis"
                )
                
            # Case 3: Scatter Plot (>=2 Numeric)
            # Only if we failed to make a bar chart (e.g. no categories?)
            # Or if user explicitly asked for correlation? Scatter is good for Price vs Rating.
            if len(numeric_cols) >= 2:
                x = numeric_cols[0]
                y = numeric_cols[1]
                label = categorical_cols[0] if categorical_cols else None
                
                return px.scatter(
                    df, x=x, y=y,
                    hover_data=[label] if label else None,
                    title=f"{x.title()} vs {y.title()}",
                    template="plotly_dark",
                    color=label if label and len(df[label].unique()) < 10 else None
                )
                
            return None
            
        except Exception as e:
            # Add logging here in real app
            print(f"Chart generation failed: {e}")
            return None
