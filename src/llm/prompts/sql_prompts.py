"""
SQL Generation Prompts - Prompts for Text-to-SQL conversion.

This module contains prompts that instruct the LLM to:
1. Understand the database schema
2. Convert natural language to SQL
3. Follow strict safety rules

Why separate prompts:
1. Easy to iterate and improve
2. Version controlled
3. Clear documentation
"""


def get_sql_system_prompt(schema_info: str) -> str:
    """
    Get the system prompt for SQL generation.
    
    Args:
        schema_info: Database schema description
        
    Returns:
        Complete system prompt for the LLM
    """
    return f"""You are a SQL expert assistant. Your job is to convert natural language questions into SQL queries.

## DATABASE SCHEMA
{schema_info}

## RULES (MUST FOLLOW)
1. Generate ONLY SELECT statements - never INSERT, UPDATE, DELETE, DROP, etc.
2. Always include a LIMIT clause (max 100 rows)
3. Only use tables and columns from the schema above
4. Return ONLY the SQL query, no explanations
5. Use backticks for table/column names with special characters
6. If you cannot generate a valid query, return: ERROR: <reason>

## EXAMPLES

User: "What are the top 5 highest rated movies?"
SQL: SELECT title, vote_average FROM movies ORDER BY vote_average DESC LIMIT 5

User: "How many movies are there?"
SQL: SELECT COUNT(*) as total_movies FROM movies LIMIT 1

User: "Show movies from 1994"
SQL: SELECT title, release_date, vote_average FROM movies WHERE release_date LIKE '1994%' LIMIT 50

User: "What's the most popular movie?"
SQL: SELECT title, popularity FROM movies ORDER BY popularity DESC LIMIT 1
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
    """
    return """You are a helpful data analytics assistant. 

Your job is to explain query results to users in a clear, concise way.

## RULES
1. Summarize the data in natural language
2. Highlight key insights (highest, lowest, totals, trends)
3. If there's no data, say so clearly
4. Be concise - 2-3 sentences max for simple queries
5. Use bullet points for lists of items
6. Include specific numbers and names from the data

## EXAMPLE

Query: SELECT title, vote_average FROM movies ORDER BY vote_average DESC LIMIT 5
Results: [{"title": "The Shawshank Redemption", "vote_average": 8.7}, ...]

Your response:
"The top 5 highest rated movies are:
• The Shawshank Redemption (8.7)
• The Godfather (8.7)
• ..."
"""


def get_answer_user_prompt(question: str, sql: str, results: list, row_count: int) -> str:
    """
    Format the results for natural language answer generation.
    
    Args:
        question: Original user question
        sql: The executed SQL query
        results: Query results as list of dicts
        row_count: Number of rows returned
        
    Returns:
        Formatted prompt for answer generation
    """
    # Limit results shown in prompt to save tokens
    display_results = results[:20] if len(results) > 20 else results
    
    return f"""User asked: "{question}"

Query executed: {sql}

Results ({row_count} rows):
{display_results}

Provide a natural language answer to the user's question based on these results."""
