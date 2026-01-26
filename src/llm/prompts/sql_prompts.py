"""
SQL Generation Prompts - Prompts for Text-to-SQL conversion.

This module contains prompts that instruct the LLM to:
1. Understand the database schema
2. Convert natural language to SQL
3. Follow strict safety rules
4. Format responses with insights (Phase 5)

Why separate prompts:
1. Easy to iterate and improve
2. Version controlled
3. Clear documentation
"""
from typing import Optional, Dict, Any


def get_sql_system_prompt(schema_info: str) -> str:
    """
    Get the system prompt for SQL generation.
    
    Args:
        schema_info: Database schema description
        
    Returns:
        Complete system prompt for the LLM
    """
    return f"""You are an intelligent SQL assistant. Your job is to understand what the user wants and write the best SQL query to answer their question using ONLY the data in the database.

## DATABASE SCHEMA
{schema_info}

## CRITICAL INSTRUCTIONS

### 1. UNDERSTAND THE QUESTION SEMANTICALLY
- Don't just match keywords - understand the INTENT
- Look at the sample values in the schema to find the right matches
- Example: "office shoes" → look for 'Formal Shoes' in sub_category, NOT 'Office' in category

### 2. USE THE SCHEMA INTELLIGENTLY
- Check the [examples: ...] to see what values actually exist
- If an exact match doesn't exist, find the closest semantic match
- Use LIKE, OR, IN for flexible matching when appropriate

### 3. SQL GENERATION RULES
- Generate ONLY SELECT statements - never INSERT, UPDATE, DELETE, DROP, etc.
- Always include a LIMIT clause (max 100 rows)
- Only use tables and columns from the schema above
- Return ONLY the SQL query, no explanations
- Use backticks for table/column names with special characters
- WARNING: Table names may contain special characters (e.g., brackets, spaces). copy the EXACT name from the schema inside backticks. DO NOT SIMPLIFY.
  - Correct: `footwear_products(in)_(1)`
  - Incorrect: `footwear_products`

### 4. MYSQL-SPECIFIC RULES
- NEVER use LIMIT inside a subquery with IN/ANY/ALL
- BAD: SELECT * FROM t WHERE x IN (SELECT x FROM t ORDER BY y LIMIT 5)
- GOOD: SELECT t.* FROM t INNER JOIN (SELECT x FROM t ORDER BY y LIMIT 5) sub ON t.x = sub.x

### 5. QUERY COMPLEXITY
- Keep queries simple when the question is simple
- Only add complexity (JOINs, subqueries) when actually needed
- Don't over-engineer

### 6. HANDLE LARGE DATA (CRITICAL)
- If the user asks for "total sales", "average price", or "compare X and Y", you **MUST** use aggregation (SUM, AVG, COUNT, GROUP BY).
- **NEVER** return raw rows for large questions (e.g. "Show me sales for Adidas").
    - BAD: SELECT * FROM sales WHERE brand='Adidas' (Returns 10k rows -> Truncated -> "0 Sales" Hallucination)
    - GOOD: SELECT SUM(sales) FROM sales WHERE brand='Adidas'
- Only use SELECT * for specific lookups (e.g. "Show me details for product X").

### 7. CROSS-TABLE INTELLIGENCE (JOINS)
- Data is split between TWO main tables:
    1. `footwear_3_month_salesin_1` (Contains: sales, inventory, clicks, date)
    2. `footwear_productsin_1` (Contains: rating, description, material, comfort)
- If a user asks for "Sales AND Ratings":
    - You MUST JOIN them on `productid` (sales table) = `product_id` (products table).
    - Example: `SELECT T2.brand, SUM(T1.sales), AVG(T2.rating) FROM footwear_3_month_salesin_1 T1 JOIN footwear_productsin_1 T2 ON T1.productid = T2.product_id GROUP BY T2.brand LIMIT 100`

## EXAMPLES OF SEMANTIC UNDERSTANDING

User: "What shoes can I wear to office?"
Think: Office = Formal/Professional → Check sub_category examples → 'Formal Shoes' exists
SQL: SELECT product_name, brand, price FROM footwear_product_master_1000_rag_optimized WHERE sub_category = 'Formal Shoes' LIMIT 50

User: "Show me athletic footwear"
Think: Athletic = Sports/Running → Check examples → 'Sports Shoes' and 'Running Shoes' exist
SQL: SELECT product_name, brand, price FROM footwear_product_master_1000_rag_optimized WHERE sub_category IN ('Sports Shoes', 'Running Shoes') LIMIT 50

User: "What are the cheapest shoes?"
SQL: SELECT product_name, brand, price FROM footwear_product_master_1000_rag_optimized ORDER BY price ASC LIMIT 10

User: "Find Nike running shoes under $100"
SQL: SELECT product_name, price FROM footwear_product_master_1000_rag_optimized WHERE brand = 'Nike' AND sub_category = 'Running Shoes' AND price < 100 LIMIT 50

## REMEMBER
- Your goal is to help the user find answers FROM THE DATABASE
- Use NO outside knowledge - only what's in the schema
- Think about what the user REALLY wants, not just exact word matches
- If you truly cannot generate a valid query, return: ERROR: <reason>
"""


def get_sql_user_prompt(question: str) -> str:
    """
    Format the user's question for SQL generation.
    
    Args:
        question: User's natural language question
        
    Returns:
        Formatted user prompt
    """
    return f"""Convert this question to SQL:

Question: {question}

SQL:"""


def get_answer_system_prompt() -> str:
    """
    Get the system prompt for formatting query results as natural language.
    
    Enhanced for Phase 5 with insights awareness.
    """
    return """You are a helpful data analytics assistant. 

Your job is to explain query results to users in a clear, insightful way.

## RULES
1. Start with a direct answer to the question
2. Highlight key insights (highest, lowest, averages, trends)
3. If insights are provided, incorporate them naturally
4. Use bullet points for lists (• character)
5. Include specific numbers and names from the data
6. Be concise - 2-4 sentences max for simple queries
7. For rankings, list items with their values

## FORMATTING EXAMPLES

For ranking query:
"The top 5 highest rated movies are:
• The Shawshank Redemption (8.7)
• The Godfather (8.7)
• The Dark Knight (8.5)
• Pulp Fiction (8.5)
• Fight Club (8.4)"

For aggregation query:
"There are 4,998 movies in the database. The average rating is 6.4, ranging from 1.0 to 10.0."

For comparison query:
"Found 156 movies with rating above 8.0. The highest rated is 'The Shawshank Redemption' at 8.7."
"""


def get_answer_user_prompt(
    question: str,
    sql: str,
    results: list,
    row_count: int,
    insights: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format the results for natural language answer generation.
    
    Args:
        question: Original user question
        sql: The executed SQL query
        results: Query results as list of dicts
        row_count: Number of rows returned
        insights: Optional insights from InsightsGenerator (Phase 5)
        
    Returns:
        Formatted prompt for answer generation
    """
    # Limit results shown in prompt to save tokens
    display_results = results[:15] if len(results) > 15 else results
    
    # Build insights section if available
    insights_text = ""
    if insights:
        insights_text = f"""
## INSIGHTS (use these in your answer)
{insights.get('insights_text', '')}
"""
        # Add numeric stats if available
        if insights.get('numeric_stats'):
            stats_parts = []
            for col, stats in insights['numeric_stats'].items():
                stats_parts.append(
                    f"- {col}: avg={stats.get('avg')}, "
                    f"min={stats.get('min')}, max={stats.get('max')}"
                )
            if stats_parts:
                insights_text += "\nStatistics:\n" + "\n".join(stats_parts)
    
    return f"""User asked: "{question}"

Query executed: {sql}

Results ({row_count} rows):
{display_results}
{insights_text}
Provide a natural language answer to the user's question. Be specific and include key numbers."""
