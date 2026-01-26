"""
Result Formatter - Format query results for display.

This module provides formatting utilities for query results:
- Markdown tables
- Bullet lists
- Summary text

The formatter automatically chooses the best format based on data shape.
"""
from typing import List, Dict, Any, Optional

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class ResultFormatter:
    """
    Formats query results into various display formats.
    
    Supports markdown tables, bullet lists, and compact summaries.
    Automatically selects the best format based on data characteristics.
    
    Example:
        >>> formatter = ResultFormatter()
        >>> data = [{"title": "Movie A", "rating": 8.5}]
        >>> print(formatter.format_as_table(data))
        | title | rating |
        |-------|--------|
        | Movie A | 8.5 |
    """
    
    def __init__(self, max_rows: int = 20, max_col_width: int = 50):
        """
        Initialize the formatter.
        
        Args:
            max_rows: Maximum rows to include in formatted output
            max_col_width: Maximum column width before truncation
        """
        self.max_rows = max_rows
        self.max_col_width = max_col_width
    
    def format_as_table(self, data: List[Dict[str, Any]]) -> str:
        """
        Format results as a markdown table.
        
        Args:
            data: List of dictionaries (query results)
            
        Returns:
            Markdown table string
        """
        if not data:
            return "_No data to display_"
        
        # Get column headers from first row
        headers = list(data[0].keys())
        
        if not headers:
            return "_No columns in data_"
        
        # Limit rows
        display_data = data[:self.max_rows]
        
        # Build header row
        header_row = "| " + " | ".join(headers) + " |"
        separator = "|" + "|".join(["---" for _ in headers]) + "|"
        
        # Build data rows
        rows = []
        for row in display_data:
            values = []
            for header in headers:
                value = self._format_value(row.get(header, ""))
                values.append(value)
            rows.append("| " + " | ".join(values) + " |")
        
        # Add truncation notice if needed
        table = "\n".join([header_row, separator] + rows)
        
        if len(data) > self.max_rows:
            table += f"\n\n_Showing {self.max_rows} of {len(data)} rows_"
        
        return table
    
    def format_as_list(
        self,
        data: List[Dict[str, Any]],
        primary_key: Optional[str] = None,
        secondary_key: Optional[str] = None
    ) -> str:
        """
        Format results as a bullet list.
        
        Args:
            data: List of dictionaries
            primary_key: Column to show first (auto-detected if None)
            secondary_key: Column to show in parentheses
            
        Returns:
            Markdown bullet list
        """
        if not data:
            return "_No data to display_"
        
        headers = list(data[0].keys())
        
        # Auto-detect primary key (first text column or first column)
        if not primary_key:
            primary_key = headers[0]
        
        # Auto-detect secondary key (first numeric column after primary)
        if not secondary_key and len(headers) > 1:
            for h in headers:
                if h != primary_key and isinstance(data[0].get(h), (int, float)):
                    secondary_key = h
                    break
            if not secondary_key:
                secondary_key = headers[1] if len(headers) > 1 else None
        
        # Build list
        lines = []
        for i, row in enumerate(data[:self.max_rows]):
            primary = self._format_value(row.get(primary_key, ""))
            
            if secondary_key and secondary_key in row:
                secondary = self._format_value(row.get(secondary_key))
                lines.append(f"• **{primary}** ({secondary})")
            else:
                lines.append(f"• {primary}")
        
        result = "\n".join(lines)
        
        if len(data) > self.max_rows:
            result += f"\n\n_...and {len(data) - self.max_rows} more_"
        
        return result
    
    def format_summary(self, data: List[Dict[str, Any]]) -> str:
        """
        Format results as a compact summary.
        
        Good for single-row results or aggregations.
        
        Args:
            data: List of dictionaries
            
        Returns:
            Summary text
        """
        if not data:
            return "_No data_"
        
        if len(data) == 1:
            # Single row - show as key: value pairs
            row = data[0]
            parts = []
            for key, value in row.items():
                formatted_value = self._format_value(value)
                parts.append(f"**{key}**: {formatted_value}")
            return " | ".join(parts)
        
        # Multiple rows - show count and sample
        return f"_{len(data)} results_"
    
    def detect_best_format(self, data: List[Dict[str, Any]]) -> str:
        """
        Detect and return the best format for the data.
        
        Args:
            data: Query results
            
        Returns:
            Format type: 'table', 'list', or 'summary'
        """
        if not data:
            return "summary"
        
        row_count = len(data)
        col_count = len(data[0].keys()) if data else 0
        
        # Single row with few columns - summary
        if row_count == 1:
            return "summary"
        
        # Few rows with ranking-style data - list
        if row_count <= 10 and col_count <= 3:
            return "list"
        
        # Default to table
        return "table"
    
    def auto_format(self, data: List[Dict[str, Any]]) -> str:
        """
        Automatically format data using the best detected format.
        
        Args:
            data: Query results
            
        Returns:
            Formatted string
        """
        format_type = self.detect_best_format(data)
        
        if format_type == "summary":
            return self.format_summary(data)
        elif format_type == "list":
            return self.format_as_list(data)
        else:
            return self.format_as_table(data)
    
    def _format_value(self, value: Any) -> str:
        """Format a single value for display."""
        if value is None:
            return "_null_"
        
        if isinstance(value, float):
            # Format floats nicely
            if value == int(value):
                return str(int(value))
            return f"{value:.2f}"
        
        str_value = str(value)
        
        # Truncate long strings
        if len(str_value) > self.max_col_width:
            return str_value[:self.max_col_width - 3] + "..."
        
        # Escape pipe characters for markdown
        return str_value.replace("|", "\\|")
