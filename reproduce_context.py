
import re
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockMemory:
    def __init__(self):
        self.messages = []
    
    def get_recent_history(self, n=10):
        # We manually structure this to match what ConversationMemory.get_recent_history() returns (dicts)
        return self.messages[-n:]

class TestSQLService:
    def __init__(self):
        self.allowed_tables = {'footwear_productsin_1'}
        
    def _extract_key_entities(self, question):
        entities = {
            'tables': [],
            'columns': [],
            'conditions': [],
            'numbers': []
        }
        for table in self.allowed_tables:
            if table.lower() in question.lower():
                entities['tables'].append(table)
        numbers = re.findall(r'\b\d+\b', question)
        entities['numbers'].extend(numbers)
        conditions = re.findall(r'\b(greater than|less than|equal to|more than|at least|top|bottom|first|last)\b', 
                           question.lower())
        entities['conditions'].extend(conditions)
        return entities
    
    def _is_follow_up_question(self, question):
        follow_up_indicators = [
            r'\b(same|similar|those|these|that|them|it)\b',
            r'\b(previous|last|earlier|above)\b',
            r'\b(also|too|additionally|furthermore)\b',
            r'\b(but|except|without|excluding)\b',
            r'\b(instead|rather than)\b',
            r'\b(compared to|versus|vs|difference)\b',
            r'\b(add|include|show me more)\b',
            r'\b(only|just|specifically)\b',
            r'\b(change|update|modify)\b',
            r'\b(and|with)\b.*\?$',
        ]
        question_lower = question.lower()
        for pattern in follow_up_indicators:
            if re.search(pattern, question_lower):
                return True
        return False
    
    def _calculate_relevance_score(self, current_question, past_question, past_sql):
        score = 0.0
        current_lower = current_question.lower()
        past_lower = past_question.lower()
        
        current_entities = self._extract_key_entities(current_question)
        past_entities = self._extract_key_entities(past_question)
        
        shared_tables = set(current_entities['tables']) & set(past_entities['tables'])
        if shared_tables:
            score += 0.4 * min(len(shared_tables) / max(len(current_entities['tables']), 1), 1.0)
        
        current_words = set(current_lower.split())
        past_words = set(past_lower.split())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'what', 'how', 'show', 'me', 'get', 'find'}
        current_words = current_words - stop_words
        past_words = past_words - stop_words
        
        if current_words and past_words:
            overlap = len(current_words & past_words) / len(current_words | past_words)
            score += 0.3 * overlap
        
        if past_sql:
            sql_lower = past_sql.lower()
            sql_entities = re.findall(r'\b(\w+)\b', sql_lower)
            current_mentions_sql_entity = any(
                entity in current_lower for entity in sql_entities 
                if len(entity) > 3
            )
            if current_mentions_sql_entity:
                score += 0.3
        
        return min(score, 1.0)
    
    def _get_history_context(self, memory, current_question=""):
        if not memory:
            return ""
        
        is_follow_up = self._is_follow_up_question(current_question)
        print(f"DEBUG: Is follow up? {is_follow_up}")
        
        n_messages = 10 if is_follow_up else 6
        recent = memory.get_recent_history(n=n_messages)
        
        if not recent:
            return ""
        
        scored_messages = []
        for i in range(0, len(recent), 2):
            if i + 1 >= len(recent):
                break
            
            user_msg = recent[i]
            assistant_msg = recent[i + 1]
            
            if user_msg['role'] != 'user' or assistant_msg['role'] != 'assistant':
                continue
            
            past_question = user_msg['content']
            past_answer = assistant_msg['content']
            past_sql = assistant_msg.get('metadata', {}).get('sql')
            past_row_count = assistant_msg.get('metadata', {}).get('row_count', 0)
            
            relevance = self._calculate_relevance_score(
                current_question, past_question, past_sql
            )
            print(f"DEBUG: Msg '{past_question}' Relevance: {relevance}")
            
            if is_follow_up or relevance > 0.2:
                scored_messages.append({
                    'question': past_question,
                    'answer': past_answer,
                    'sql': past_sql,
                    'row_count': past_row_count,
                    'relevance': relevance,
                    'index': i // 2
                })
        
        if not scored_messages:
            return ""
        
        scored_messages.sort(key=lambda x: (-x['relevance'], -x['index']))
        max_context_pairs = 3 if is_follow_up else 2
        relevant_messages = scored_messages[:max_context_pairs]
        relevant_messages.sort(key=lambda x: x['index'])
        
        context_parts = []
        if is_follow_up:
            context_parts.append("\n=== CONVERSATION CONTEXT (Follow-up detected) ===")
        else:
            context_parts.append("\n=== RELEVANT CONVERSATION HISTORY ===")
        
        for idx, msg in enumerate(relevant_messages, 1):
            context_parts.append(f"\n[Q{idx}] {msg['question']}")
            if msg['sql']:
                context_parts.append(f"   [SQL Used: {msg['sql']}]")
            context_parts.append(f"[A{idx}] {msg['answer'][:50]}...")
            
        context_parts.append("\n=== END OF CONTEXT ===")
        context_parts.append("\nIMPORTANT: If the current question refers to 'same', 'those', 'that', etc., reuse the relevant SQL filters, tables, and conditions from above.\n")
        
        return "\n".join(context_parts)

def test_logic():
    print("--- Testing Logic Safely ---")
    mock_memory = MockMemory()
    
    # 1. Populate History
    q1 = "tell me the best shoes for officewear"
    sql1 = "SELECT product_name FROM footwear_productsin_1 WHERE sub_category = 'Formal Shoes' LIMIT 10"
    ans1 = "The best shoes..."
    
    mock_memory.messages.append({'role': 'user', 'content': q1, 'metadata': {}})
    mock_memory.messages.append({'role': 'assistant', 'content': ans1, 'metadata': {'sql': sql1, 'row_count': 10}})
    
    # 2. Test
    service = TestSQLService()
    current_q = "from the given list give me the red ones only"
    
    context = service._get_history_context(mock_memory, current_q)
    
    print("\n--- RESULT ---")
    print(context)
    print("--------------")
    
    if "Formal Shoes" in context:
        print("✅ SUCCESS: Context preserved!")
    else:
        print("❌ FAILURE: Context lost.")

if __name__ == "__main__":
    test_logic()
