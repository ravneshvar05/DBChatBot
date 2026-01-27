"""
Insights Generator - Automatic data analysis and insights.

This module analyzes query results and generates:
- Numeric statistics (min, max, avg, sum)
- Distribution analysis
- Key insights text

These insights are provided to the LLM for better answers.
"""
from typing import List, Dict, Any, Optional
from statistics import mean, median, stdev
from collections import Counter

from src.core.logging_config import get_logger
from src.core.config import get_settings
from src.llm.client import LLMClient
from src.llm.prompts.analysis_prompts import DEEP_MODE_SYSTEM_PROMPT

logger = get_logger(__name__)


class InsightsGenerator:
    """
    Generates automatic insights from query results.
    
    Analyzes data to find patterns, statistics, and notable values.
    Uses LLM (Gemini) for high-level insight generation.
    
    Example:
        >>> generator = InsightsGenerator()
        >>> data = [{"title": "A", "rating": 8.5}, {"title": "B", "rating": 9.0}]
        >>> insights = generator.generate_insights(data)
        >>> print(insights["insights_text"])
        "Average rating is 8.75. Highest: 9.0, Lowest: 8.5"
    """

    def __init__(self):
        """Initialize with LLM client."""
        self.settings = get_settings()
        self.llm = LLMClient()
        logger.info("InsightsGenerator initialized")
    
    def generate_insights(
        self,
        data: List[Dict[str, Any]],
        query_type: Optional[str] = None,
        include_analysis: bool = False
    ) -> Dict[str, Any]:
        """
        Generate comprehensive insights from data.
        
        Args:
            data: Query results
            query_type: Optional query classification
            include_analysis: If True, force deep AI analysis
        """
        if not data:
            return {
                "row_count": 0,
                "numeric_stats": {},
                "top_values": {},
                "insights_text": "No data returned."
            }
        
        insights = {
            "row_count": len(data),
            "numeric_stats": {},
            "top_values": {},
            "column_types": {},
            "insights_text": "",
            "insight_type": "simple"  # Default to simple
        }
        
        # Analyze each column
        columns = list(data[0].keys())
        
        for col in columns:
            values = [row.get(col) for row in data if row.get(col) is not None]
            
            if not values:
                continue
            
            col_type = self._detect_column_type(values)
            insights["column_types"][col] = col_type
            
            if col_type == "numeric":
                stats = self._analyze_numeric(values)
                insights["numeric_stats"][col] = stats
                
                # Track top value for numeric columns
                if data:
                    max_row = max(data, key=lambda r: r.get(col, 0) if isinstance(r.get(col), (int, float)) else 0)
                    insights["top_values"][col] = {
                        "value": max_row.get(col),
                        "row": max_row
                    }
            
            elif col_type == "text":
                # Just track the first text column values
                if col not in insights["top_values"]:
                    insights["top_values"][col] = values[0] if values else None
        
        # Generate human-readable insights text
        # OPTIMIZATION: STRICTLY respect the toggle.
        # If include_analysis is True -> AI Mode (Executive Brief)
        # If include_analysis is False -> Simple Mode (Basic Stats only)
        
        if include_analysis:
            insights["insights_text"] = self._generate_ai_insights(
                data, insights, query_type
            )
            insights["insight_type"] = "ai"
        else:
            # Fallback to simple rule-based text (Fast Mode)
            # This is NOT an executive brief, just a summary.
            insights["insights_text"] = self._generate_simple_text(insights)
            insights["insight_type"] = "simple"
        
        return insights
    
    def _detect_column_type(self, values: List[Any]) -> str:
        """Detect if a column is numeric or text."""
        numeric_count = sum(1 for v in values if isinstance(v, (int, float)))
        
        if numeric_count > len(values) * 0.8:
            return "numeric"
        return "text"
    
    def _analyze_numeric(self, values: List[Any]) -> Dict[str, Any]:
        """
        Calculate statistics for numeric values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Dictionary with min, max, avg, sum, etc.
        """
        # Filter to only numeric values
        nums = [v for v in values if isinstance(v, (int, float))]
        
        if not nums:
            return {}
        
        stats = {
            "min": min(nums),
            "max": max(nums),
            "avg": round(mean(nums), 2),
            "sum": round(sum(nums), 2),
            "count": len(nums)
        }
        
        # Add median if enough values
        if len(nums) >= 3:
            stats["median"] = round(median(nums), 2)
        
        # Add standard deviation if enough values
        if len(nums) >= 3:
            try:
                stats["std_dev"] = round(stdev(nums), 2)
            except:
                pass
        
        return stats
    
    def analyze_distribution(
        self,
        data: List[Dict[str, Any]],
        column: str
    ) -> Dict[str, Any]:
        """
        Analyze value distribution for a column.
        
        Args:
            data: Query results
            column: Column to analyze
            
        Returns:
            Distribution info (unique count, top values)
        """
        values = [row.get(column) for row in data if row.get(column) is not None]
        
        if not values:
            return {"unique_count": 0, "top_values": []}
        
        counter = Counter(values)
        
        return {
            "unique_count": len(counter),
            "top_values": counter.most_common(5),
            "total_count": len(values)
        }
    
    def _generate_ai_insights(
        self,
        data: List[Dict[str, Any]],
        stats: Dict[str, Any],
        query_type: Optional[str] = None
    ) -> str:
        """Generate human-readable insights using Gemini."""
        try:
            # Prepare data summary for prompt 
            # STRICT DATA CONTRACT: Deep Analysis gets ONLY derived metrics. NO raw data.
            # We strictly filter what goes into the prompt.
            
            stats_context = {
                "numeric_stats": stats.get("numeric_stats", {}),
                "top_values": stats.get("top_values", {}),
                "column_types": stats.get("column_types", {})
            }
            stats_summary = str(stats_context)
            
            prompt = f"""
            Analyze the following statistical metrics.
            
            Context:
            - Query Type: {query_type}
            - Row Count: {len(data)}
            - Statistics: {stats_summary}
            
            Task:
            Write the Executive Brief.
            """
            
            response = self.llm.generate(
                user_message=prompt,
                system_prompt=DEEP_MODE_SYSTEM_PROMPT,
                model=self.settings.llm_model_analysis
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate AI insights: {e}")
            return "Unable to generate detailed insights at this time."

    def _generate_simple_text(self, insights: Dict[str, Any]) -> str:
        """Generate simple rule-based insights (Fast Mode)."""
        parts = []
        row_count = insights["row_count"]
        parts.append(f"Found {row_count} records.")
        
        # Add numeric stats summary
        for col, stats in insights.get("numeric_stats", {}).items():
            if "avg" in stats:
                display_col = col.replace("_", " ").title()
                parts.append(f"{display_col}: Avg {stats['avg']}, Range {stats['min']}-{stats['max']}.")
                
        return " ".join(parts)
