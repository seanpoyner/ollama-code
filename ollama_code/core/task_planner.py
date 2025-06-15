"""Task planning using Ollama"""

import json
import re
import logging
from typing import List, Dict, Tuple
import ollama

from .todos import TodoPriority

logger = logging.getLogger(__name__)


class AITaskPlanner:
    """Uses AI to intelligently plan tasks based on user requests"""
    
    def __init__(self, model_name: str):
        self.model = model_name
    
    def plan_tasks(self, user_request: str) -> Tuple[List[Dict], str]:
        """
        Use AI to analyze the request and create a task plan
        Returns: (tasks, explanation)
        """
        # Create a focused prompt for task planning
        prompt = f"""You are a task planning assistant. Analyze the following request and create a detailed task plan.

User Request: {user_request}

Create a list of specific, actionable tasks needed to complete this request. For each task:
1. Be specific about what needs to be done
2. Order tasks logically (dependencies first)
3. Assign priorities: HIGH (critical path), MEDIUM (important but not blocking), LOW (nice to have)

Format your response as:
TASK_PLAN_START
1. [HIGH] Task description here
2. [MEDIUM] Another task description
3. [LOW] Final task description
TASK_PLAN_END

Then provide a brief explanation of your approach.

Important guidelines:
- Create tasks specific to the actual request, not generic steps
- Include technical implementation details in task names
- Typical task count: 4-8 tasks
- First task should analyze/understand requirements by ACTUALLY exploring files
- Include "create X file" or "implement Y function" in task names
- Make tasks concrete and actionable, not vague

CRITICAL FOR ANALYSIS TASKS:
- When a task involves analyzing, reviewing, or understanding code/files:
  * The task MUST explicitly state to "read files completely"
  * Include "thoroughly explore the codebase" in the task description
  * Mention specific file reading tools (Read, Glob, Grep) in the task
  * Example: "Thoroughly analyze the codebase structure by reading all relevant files completely using Read tool"
- NEVER make assumptions about file contents - always read them fully
- Analysis tasks should emphasize complete exploration over quick scanning
- If reviewing code, the task should mention reading the entire file, not just parts
"""

        try:
            # Get AI response
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You are a helpful task planning assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                options={
                    'temperature': 0.7,
                    'top_p': 0.9
                }
            )
            
            ai_response = response['message']['content']
            logger.info(f"AI task planning response: {ai_response[:200]}...")
            
            # Extract tasks from response
            tasks = self._parse_tasks_from_response(ai_response)
            
            # Extract explanation
            explanation = self._extract_explanation(ai_response)
            
            return tasks, explanation
            
        except Exception as e:
            logger.error(f"Error in AI task planning: {e}")
            # Fallback to a simple default
            return self._get_fallback_tasks(user_request)
    
    def _parse_tasks_from_response(self, response: str) -> List[Dict]:
        """Parse tasks from AI response"""
        tasks = []
        
        # Find content between markers
        match = re.search(r'TASK_PLAN_START\s*(.*?)\s*TASK_PLAN_END', response, re.DOTALL)
        if not match:
            # Try to find numbered list
            lines = response.split('\n')
            task_lines = []
            for line in lines:
                if re.match(r'^\d+\.?\s*\[', line):
                    task_lines.append(line)
        else:
            task_content = match.group(1)
            task_lines = task_content.strip().split('\n')
        
        # Parse each task line
        for line in task_lines:
            line = line.strip()
            if not line:
                continue
                
            # Match patterns like "1. [HIGH] Task description" or "1. Task description [HIGH]"
            match = re.match(r'^\d+\.?\s*\[(\w+)\]\s*(.+)', line)
            if not match:
                match = re.match(r'^\d+\.?\s*(.+)\s*\[(\w+)\]', line)
                if match:
                    priority_str, task_name = match.group(2), match.group(1)
                else:
                    # No priority found, assume MEDIUM
                    match = re.match(r'^\d+\.?\s*(.+)', line)
                    if match:
                        task_name = match.group(1)
                        priority_str = "MEDIUM"
                    else:
                        continue
            else:
                priority_str, task_name = match.group(1), match.group(2)
            
            # Map priority
            priority_map = {
                "HIGH": TodoPriority.HIGH,
                "MEDIUM": TodoPriority.MEDIUM,
                "LOW": TodoPriority.LOW
            }
            priority = priority_map.get(priority_str.upper(), TodoPriority.MEDIUM)
            
            tasks.append({
                "name": task_name.strip(),
                "priority": priority
            })
        
        # If no tasks found, return empty list
        if not tasks:
            logger.warning("No tasks found in AI response")
            return []
            
        return tasks
    
    def _extract_explanation(self, response: str) -> str:
        """Extract the explanation part after the task list"""
        # Look for content after TASK_PLAN_END
        parts = response.split('TASK_PLAN_END')
        if len(parts) > 1:
            explanation = parts[1].strip()
            # Take first paragraph or few sentences
            lines = explanation.split('\n')
            explanation_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('TASK_'):
                    explanation_lines.append(line)
                    if len(explanation_lines) >= 3:  # Limit to 3 lines
                        break
            return '\n'.join(explanation_lines)
        
        # Fallback: look for explanation keywords
        lines = response.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['approach', 'plan', 'will', 'first', 'then']):
                return line.strip()
        
        return "I'll work through these tasks systematically to complete your request."
    
    def _get_fallback_tasks(self, request: str) -> Tuple[List[Dict], str]:
        """Fallback task generation if AI fails"""
        logger.info("Using fallback task generation")
        
        # Create a truncated version for display, but preserve full context
        display_request = request if len(request) <= 100 else request[:97] + "..."
        
        # Check if this is an analysis/review request
        analysis_keywords = ['analyze', 'review', 'understand', 'explore', 'examine', 'investigate']
        is_analysis = any(keyword in request.lower() for keyword in analysis_keywords)
        
        # Create basic tasks based on request keywords
        if is_analysis:
            tasks = [
                {"name": f"Thoroughly analyze requirements and explore codebase by reading all relevant files completely: {display_request}", "priority": TodoPriority.HIGH},
                {"name": "Design the implementation approach based on complete file analysis", "priority": TodoPriority.HIGH},
                {"name": "Implement the main functionality", "priority": TodoPriority.HIGH},
                {"name": "Test and validate the implementation", "priority": TodoPriority.MEDIUM},
                {"name": "Document the solution", "priority": TodoPriority.LOW}
            ]
        else:
            tasks = [
                {"name": f"Analyze requirements: {display_request}", "priority": TodoPriority.HIGH},
                {"name": "Design the implementation approach", "priority": TodoPriority.HIGH},
                {"name": "Implement the main functionality", "priority": TodoPriority.HIGH},
                {"name": "Test and validate the implementation", "priority": TodoPriority.MEDIUM},
                {"name": "Document the solution", "priority": TodoPriority.LOW}
            ]
        
        explanation = "I'll break this down into systematic steps to complete your request."
        
        return tasks, explanation