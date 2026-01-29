import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

def get_llm_agent(model_name, temperature=0.2):
    """
    Factory function to return correct Langchain LLM object based on the model string. 
    """
    # ensure that OpenAI, Anthropic, Google Keys set in environment variables before running
    if "gpt" in model_name:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing")
        
        return ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)

    elif "claude" in model_name:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is missing")
        
        return ChatAnthropic(model=model_name, temperature=temperature, api_key=api_key)
    
    elif "gemini" in model_name:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing")
        
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, api_key=api_key)
    
    elif "llama" in model_name:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing")
        
        return ChatGroq(model=model_name, temperature=temperature, api_key=api_key)
    
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    