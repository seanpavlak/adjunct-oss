"""
LLM-based response generator for Canvas discussions
"""

import os
import json
import difflib
import random
from typing import List, Tuple, Literal
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

class Response(BaseModel):
    value: str

@dataclass
class ResponseGenerator:
    week: int = field(init=True, repr=False)
    course_selector: str = field(init=True, repr=False, default="A")
    provider: Literal["openai", "anthropic", "deepseek"] = field(init=True, repr=False, default="openai")
    openai_key: str = field(init=True, repr=False, default="")
    anthropic_key: str = field(init=True, repr=False, default="")
    deepseek_key: str = field(init=True, repr=False, default="")
    llm: BaseChatModel = field(init=False)
    prompt: PromptTemplate = field(init=False, default=None)


    def _get_week_prompt(self) -> str:
        courses_path = os.path.join(os.path.dirname(__file__), 'courses.json')
        if not os.path.exists(courses_path):
            raise FileNotFoundError(f"courses.json not found: {courses_path}")
        
        with open(courses_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        courses = config.get('courses', {})
        if not courses:
            raise ValueError("No courses found in courses.json")
        
        if self.course_selector in courses:
            course = courses[self.course_selector]
        else:
            course = next((c for c in courses.values() if c.get('course_id') == str(self.course_selector)), None)
        
        if not course:
            raise ValueError(f"Course '{self.course_selector}' not found in courses.json")
        
        weeks = course.get('weeks', {})
        week_data = weeks.get(str(self.week))
        
        if not week_data:
            raise ValueError(f"Week {self.week} data not found in course {self.course_selector}")
        
        prompt = week_data.get('discussion_prompt')
        if not prompt:
            raise ValueError(f"No discussion prompt found for week {self.week} in course {self.course_selector}")
        
        return prompt

    def __post_init__(self):
        # Initialize LLM based on provider
        self.llm = self._initialize_llm()
        self.parser = JsonOutputParser(pydantic_object=Response)
        dq_prompt_text = self._get_week_prompt()
        base_template = ('I need you to analyze this CSV, column "Post" is the students initial reply to the prompt, and column "Response" is my feedback. Then understand how it relates to this prompt:\n{dq_prompt}\n\n'
                        'Student and Professor Response Examples:\n{examples}\n\n'
                        'I need you to read this reply, and respond with simple short 3-4 sentence feedback (max 80 words) that a college student would understand and it has to be in the exact same style as the replies in the listed csv:\n{content}\n\n'
                        '{format_instructions}\n\n'
                        'Guidelines: Match the tone and style exactly from the examples. Use natural, human language like {preferred_phrases}. Strike a balance between friendly and professional - sound like a real person, not an AI. Avoid generic phrases like "good job" or "well done". Never use exclamation marks. Avoid formulaic closing sentences that start with "Keep..." or end with encouraging phrases about future learning.')
        
        self.follow_up_instruction = ' Additionally, ask a thoughtful follow-up question to deepen the student\'s thinking.'
        
        # Phrases to randomly inject into prompts
        self.preferred_phrases = [
            'awesome',
            'spot on', 
            'it\'s really interesting that',
            'that\'s a great point',
            'I like how you',
            'that\'s exactly right',
            'nice observation',
            'you\'re onto something there'
        ]
        
        self.prompt = PromptTemplate(
            template=base_template,
            input_variables=["content", "examples", "preferred_phrases"],
            partial_variables={
                "dq_prompt": dq_prompt_text,
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    def _initialize_llm(self) -> BaseChatModel:
        """Initialize the appropriate LLM based on the provider"""
        if self.provider == "openai":
            if not self.openai_key:
                raise ValueError("OpenAI API key is required when using OpenAI provider")
            return ChatOpenAI(
                model="gpt-4o",
                temperature=0.8,
                openai_api_key=self.openai_key,
                verbose=True
            )
        elif self.provider == "anthropic":
            if not self.anthropic_key:
                raise ValueError("Anthropic API key is required when using Anthropic provider")
            return ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.8,
                anthropic_api_key=self.anthropic_key,
                verbose=True
            )
        elif self.provider == "deepseek":
            if not self.deepseek_key:
                raise ValueError("DeepSeek API key is required when using DeepSeek provider")
            # DeepSeek uses OpenAI-compatible API
            return ChatOpenAI(
                model="deepseek-chat",
                temperature=0.8,
                openai_api_key=self.deepseek_key,
                base_url="https://api.deepseek.com/v1",
                verbose=True
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _load_discussion_examples(self) -> List[Tuple[str, str]]:
        """Load discussion examples from courses.json instead of CSV files"""
        courses_path = os.path.join(os.path.dirname(__file__), 'courses.json')
        if not os.path.exists(courses_path):
            raise FileNotFoundError(f"courses.json not found: {courses_path}")
        
        with open(courses_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        courses = config.get('courses', {})
        if not courses:
            raise ValueError("No courses found in courses.json")
        
        if self.course_selector in courses:
            course = courses[self.course_selector]
        else:
            course = next((c for c in courses.values() if c.get('course_id') == str(self.course_selector)), None)
        
        if not course:
            raise ValueError(f"Course '{self.course_selector}' not found in courses.json")
        
        weeks = course.get('weeks', {})
        week_data = weeks.get(str(self.week))
        
        if not week_data:
            raise ValueError(f"Week {self.week} data not found in course {self.course_selector}")
        
        discussion_data = week_data.get('discussion_data', [])
        if not discussion_data:
            raise ValueError(f"No discussion data found for week {self.week} in course {self.course_selector}")
        
        examples: List[Tuple[str, str]] = []
        for item in discussion_data:
            post = item.get('post', '').strip()
            response = item.get('response', '').strip()
            if post and response:
                examples.append((post, response))
        
        return examples


    def _select_few_shots(self, content: str, examples: List[Tuple[str, str]], k: int = 3) -> List[Tuple[str, str]]:
        def score(example_post: str) -> float:
            return difflib.SequenceMatcher(None, content.lower(), example_post.lower()).ratio()
        ranked = sorted(examples, key=lambda pr: score(pr[0]), reverse=True)
        return ranked[:k]

    def _format_examples(self, few_shots: List[Tuple[str, str]]) -> str:
        lines: List[str] = []
        for post, response in few_shots:
            lines.append(f"Post: {post[:1000]}\nResponse: {response[:800]}")
        return "\n\n".join(lines)
    
    def _generate_preferred_phrases(self) -> str:
        """Generate a random combination of preferred phrases (always at least 1)"""
        # Always include at least one phrase
        selected_phrases = [random.choice(self.preferred_phrases)]
        
        # Randomly add more phrases (30% chance for each additional phrase)
        for phrase in self.preferred_phrases:
            if phrase not in selected_phrases and random.random() < 0.3:
                selected_phrases.append(phrase)
        
        # Format as comma-separated list with "and" before the last item
        if len(selected_phrases) == 1:
            return f'"{selected_phrases[0]}"'
        elif len(selected_phrases) == 2:
            return f'"{selected_phrases[0]}" and "{selected_phrases[1]}"'
        else:
            return f'"{", ".join(selected_phrases[:-1])}" and "{selected_phrases[-1]}"'
        
    def reply(self, content) -> str:
        if not self.llm:
            print("Error: No LLM Init'd")
            return None 
        examples = self._load_discussion_examples()
        few_shots = self._select_few_shots(content, examples, k=3)
        examples_text = self._format_examples(few_shots)
        preferred_phrases = self._generate_preferred_phrases()

        if random.random() < 0.05:
            modified_template = self.prompt.template + self.follow_up_instruction
            modified_prompt = PromptTemplate(
                template=modified_template,
                input_variables=self.prompt.input_variables,
                partial_variables=self.prompt.partial_variables
            )
            chain = modified_prompt | self.llm | self.parser
        else:
            chain = self.prompt | self.llm | self.parser
        
        response = chain.invoke({
            "content": content,
            "examples": examples_text,
            "preferred_phrases": preferred_phrases,
        })
        return response['value']

